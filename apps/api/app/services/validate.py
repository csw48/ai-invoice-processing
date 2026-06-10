import re
from datetime import datetime

from app.country_profiles import CountryProfile, detect_country
from app.models import ClientConfig, ConfidenceValue, ExtractedInvoice, ValidationIssue, ValidationReport


def _is_number(value) -> bool:
    # bool is a subclass of int — exclude it so True/False never count as amounts.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


_DATE_PATTERN_TO_STRPTIME = {
    "DD.MM.YYYY": "%d.%m.%Y",
    "D.M.YYYY": "%d.%m.%Y",
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "M/D/YYYY": "%m/%d/%Y",
    "YYYY-MM-DD": "%Y-%m-%d",
    "DD-MM-YYYY": "%d-%m-%Y",
}


def _matches_any_date_format(value: str, formats: tuple[str, ...]) -> bool:
    for fmt in formats:
        py_fmt = _DATE_PATTERN_TO_STRPTIME.get(fmt)
        if not py_fmt:
            continue
        try:
            datetime.strptime(value, py_fmt)
            return True
        except ValueError:
            continue
    return False


def _profile_for(extracted: ExtractedInvoice, config: ClientConfig) -> CountryProfile:
    return detect_country(
        explicit_code=getattr(config, "country_code", None),
        vendor_vat=extracted.vendor_vat.value if extracted.vendor_vat else None,
        currency=extracted.currency.value if extracted.currency else None,
    )


def validate_invoice(extracted: ExtractedInvoice, config: ClientConfig) -> ValidationReport:
    issues: list[ValidationIssue] = []
    profile = _profile_for(extracted, config)

    for field in config.fields_required:
        item = getattr(extracted, field, None)
        # Skip non-scalar fields (e.g. line_items) — a misconfigured required list
        # must not crash the validator with an AttributeError.
        if not isinstance(item, ConfidenceValue):
            continue
        if item.value in (None, ""):
            issues.append(ValidationIssue(field=field, severity="error", message="Required field is missing"))
        elif item.confidence < config.confidence_threshold:
            issues.append(ValidationIssue(field=field, severity="warning", message="Low confidence field"))

    # VAT format: only enforce if profile has a VAT regex (some countries don't, like US)
    vat = extracted.vendor_vat.value
    if vat and profile.vat_format:
        if not re.fullmatch(profile.vat_format, str(vat)):
            issues.append(ValidationIssue(
                field="vendor_vat",
                severity="error",
                message=f"Invalid {profile.name} VAT format",
            ))

    # Currency: if client config explicitly overrides, prefer that; otherwise use profile.
    explicit_allowed = (config.validation_rules or {}).get("allowed_currencies") if config.validation_rules else None
    allowed_currencies = explicit_allowed or list(profile.allowed_currencies)
    currency = extracted.currency.value
    if currency and allowed_currencies and currency not in allowed_currencies:
        issues.append(ValidationIssue(
            field="currency",
            severity="warning",
            message=f"Currency {currency} is unusual for {profile.name}",
        ))

    # Dates: check at least one of the profile's date formats matches.
    for date_field in ("invoice_date", "due_date"):
        item = getattr(extracted, date_field)
        if item.value and not _matches_any_date_format(str(item.value), profile.date_formats):
            issues.append(ValidationIssue(
                field=date_field,
                severity="warning",
                message=f"Date format unusual for {profile.name} (got: {item.value})",
            ))

    # Totals — brief Step 3 codes E02 / E03.
    # Model mapping: subtotal = net, vat_amount = tax, total_amount = gross.
    net = extracted.subtotal.value
    tax = extracted.vat_amount.value
    gross = extracted.total_amount.value
    components = {"subtotal": net, "vat_amount": tax, "total_amount": gross}
    missing = [name for name, value in components.items() if not _is_number(value)]
    if missing:
        # E02 — incomplete monetary breakdown. A warning, not an error: many real
        # invoices expose only the gross total, and that must stay approvable.
        issues.append(ValidationIssue(
            field="total_amount",
            severity="warning",
            code="E02",
            message=f"Incomplete totals — missing or non-numeric: {', '.join(missing)}",
        ))
    else:
        # E03 — verify existence/number FIRST (above), THEN round each to 2 decimals
        # before comparing, so float artefacts don't trigger a false mismatch.
        if round(net + tax, 2) != round(gross, 2):
            issues.append(ValidationIssue(
                field="total_amount",
                severity="error",
                code="E03",
                message="Net plus tax does not equal gross",
            ))

    # If tax_lines are present, their amounts should sum to vat_amount.
    if extracted.tax_lines and _is_number(tax):
        tax_line_sum = round(sum(tl.amount for tl in extracted.tax_lines), 2)
        if abs(tax_line_sum - round(tax, 2)) > 0.01:
            issues.append(ValidationIssue(
                field="vat_amount",
                severity="warning",
                code="E02",
                message=f"Tax lines sum ({tax_line_sum}) differs from vat_amount ({round(tax, 2)})",
            ))

    # E04 — incomplete supplier (sender) data. Warning so partial extractions stay
    # approvable; the vendor name is the minimum, plus VAT where the country uses one.
    supplier_missing = []
    if not extracted.vendor_name.value:
        supplier_missing.append("vendor_name")
    if profile.vat_format and not extracted.vendor_vat.value:
        supplier_missing.append("vendor_vat")
    if supplier_missing:
        issues.append(ValidationIssue(
            field="vendor_name",
            severity="warning",
            code="E04",
            message=f"Incomplete supplier data — missing: {', '.join(supplier_missing)}",
        ))

    # E05 — incomplete recipient (buyer) data. Only fires once a recipient was
    # actually identified (recipient_name present); invoices with no recipient at
    # all are common and must not warn.
    if extracted.recipient_name.value:
        recipient_missing = [
            f for f in ("recipient_address", "recipient_city")
            if not getattr(extracted, f).value
        ]
        if recipient_missing:
            issues.append(ValidationIssue(
                field="recipient_name",
                severity="warning",
                code="E05",
                message=f"Incomplete recipient data — missing: {', '.join(recipient_missing)}",
            ))

    return ValidationReport(
        valid=not any(issue.severity == "error" for issue in issues),
        issues=issues,
    )
