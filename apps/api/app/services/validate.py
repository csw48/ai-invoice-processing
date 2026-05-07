import re
from datetime import datetime

from app.country_profiles import CountryProfile, detect_country
from app.models import ClientConfig, ExtractedInvoice, ValidationIssue, ValidationReport


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
        item = getattr(extracted, field)
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

    # VAT math: subtotal + vat_amount = total (within 0.01)
    subtotal = extracted.subtotal.value
    vat_amount = extracted.vat_amount.value
    total = extracted.total_amount.value
    if all(isinstance(v, (int, float)) for v in [subtotal, vat_amount, total]):
        if abs((subtotal + vat_amount) - total) > 0.01:
            issues.append(ValidationIssue(
                field="total_amount",
                severity="error",
                message="Subtotal plus VAT does not match total",
            ))

    return ValidationReport(
        valid=not any(issue.severity == "error" for issue in issues),
        issues=issues,
    )
