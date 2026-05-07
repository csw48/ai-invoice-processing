import re

from app.models import ClientConfig, ExtractedInvoice, ValidationIssue, ValidationReport


def validate_invoice(extracted: ExtractedInvoice, config: ClientConfig) -> ValidationReport:
    issues: list[ValidationIssue] = []

    for field in config.fields_required:
        item = getattr(extracted, field)
        if item.value in (None, ""):
            issues.append(ValidationIssue(field=field, severity="error", message="Required field is missing"))
        elif item.confidence < config.confidence_threshold:
            issues.append(ValidationIssue(field=field, severity="warning", message="Low confidence field"))

    vat = extracted.vendor_vat.value
    vat_format = config.validation_rules.get("vat_format")
    if vat and vat_format and not re.fullmatch(vat_format, str(vat)):
        issues.append(ValidationIssue(field="vendor_vat", severity="error", message="Invalid Slovak VAT format"))

    currency = extracted.currency.value
    allowed = config.validation_rules.get("allowed_currencies", [])
    if currency and allowed and currency not in allowed:
        issues.append(ValidationIssue(field="currency", severity="error", message="Currency is not allowed"))

    subtotal = extracted.subtotal.value
    vat_amount = extracted.vat_amount.value
    total = extracted.total_amount.value
    if all(isinstance(v, (int, float)) for v in [subtotal, vat_amount, total]):
        if abs((subtotal + vat_amount) - total) > 0.01:
            issues.append(ValidationIssue(field="total_amount", severity="error", message="Subtotal plus VAT does not match total"))

    return ValidationReport(valid=not any(issue.severity == "error" for issue in issues), issues=issues)
