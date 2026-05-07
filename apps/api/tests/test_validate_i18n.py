from app.models import ClientConfig, ConfidenceValue, ExtractedInvoice
from app.services.validate import validate_invoice


def _build_extracted(**overrides) -> ExtractedInvoice:
    base = dict(
        vendor_name=ConfidenceValue(value="Vendor", confidence=0.95),
        invoice_number=ConfidenceValue(value="INV-1", confidence=0.95),
        invoice_date=ConfidenceValue(value="07.05.2026", confidence=0.95),
        total_amount=ConfidenceValue(value=100.0, confidence=0.95),
        currency=ConfidenceValue(value="EUR", confidence=0.95),
    )
    base.update(overrides)
    return ExtractedInvoice(**base)


def test_us_invoice_in_usd_passes_validation():
    extracted = _build_extracted(
        currency=ConfidenceValue(value="USD", confidence=0.95),
        invoice_date=ConfidenceValue(value="05/07/2026", confidence=0.95),
        vendor_vat=ConfidenceValue(value=None, confidence=0.0),
    )
    config = ClientConfig(country_code="US", fields_required=["vendor_name", "invoice_number", "invoice_date", "total_amount"])

    report = validate_invoice(extracted, config)

    assert report.valid is True
    assert all(issue.severity != "error" for issue in report.issues)


def test_de_invoice_with_de_vat_passes_validation():
    extracted = _build_extracted(
        vendor_vat=ConfidenceValue(value="DE123456789", confidence=0.95),
        invoice_date=ConfidenceValue(value="03.05.2026", confidence=0.95),
    )
    config = ClientConfig()

    report = validate_invoice(extracted, config)

    assert report.valid is True


def test_sk_invoice_with_invalid_vat_format_fails_validation():
    extracted = _build_extracted(
        vendor_vat=ConfidenceValue(value="SK12345", confidence=0.95),  # too short
        invoice_date=ConfidenceValue(value="07.05.2026", confidence=0.95),
    )
    config = ClientConfig(country_code="SK")

    report = validate_invoice(extracted, config)

    assert report.valid is False
    assert any(issue.field == "vendor_vat" and issue.severity == "error" for issue in report.issues)


def test_country_auto_detected_from_vat_prefix_when_config_has_no_country():
    extracted = _build_extracted(
        vendor_vat=ConfidenceValue(value="FRAB123456789", confidence=0.95),
        currency=ConfidenceValue(value="EUR", confidence=0.95),
        invoice_date=ConfidenceValue(value="07/05/2026", confidence=0.95),
    )
    # Default config has no country_code; FR profile should be picked up.
    config = ClientConfig()

    report = validate_invoice(extracted, config)

    # FR uses DD/MM/YYYY which matches; should be valid.
    assert report.valid is True


def test_unusual_currency_for_country_yields_warning_not_error():
    extracted = _build_extracted(
        vendor_vat=ConfidenceValue(value="SK1234567890", confidence=0.95),
        currency=ConfidenceValue(value="USD", confidence=0.95),  # SK invoice in USD
        invoice_date=ConfidenceValue(value="07.05.2026", confidence=0.95),
    )
    config = ClientConfig(country_code="SK")

    report = validate_invoice(extracted, config)

    # No errors; currency mismatch is a warning so the user can still approve.
    assert report.valid is True
    assert any(issue.field == "currency" and issue.severity == "warning" for issue in report.issues)
