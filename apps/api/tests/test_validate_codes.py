"""Tests for the brief Step 3 structured error codes (E02-E05) in the validator."""
from app.models import ClientConfig, ConfidenceValue, ExtractedInvoice
from app.services.validate import validate_invoice


def _full(**overrides) -> ExtractedInvoice:
    base = dict(
        vendor_name=ConfidenceValue(value="Vendor", confidence=0.95),
        vendor_vat=ConfidenceValue(value="SK1234567890", confidence=0.95),
        invoice_number=ConfidenceValue(value="INV-1", confidence=0.95),
        invoice_date=ConfidenceValue(value="07.05.2026", confidence=0.95),
        subtotal=ConfidenceValue(value=100.0, confidence=0.95),
        vat_amount=ConfidenceValue(value=20.0, confidence=0.95),
        total_amount=ConfidenceValue(value=120.0, confidence=0.95),
        currency=ConfidenceValue(value="EUR", confidence=0.95),
    )
    base.update(overrides)
    return ExtractedInvoice(**base)


def _codes(report) -> set[str]:
    return {i.code for i in report.issues if i.code}


def test_e02_when_breakdown_incomplete_is_a_warning_not_error():
    extracted = _full(vat_amount=ConfidenceValue(value=None, confidence=0.0))
    report = validate_invoice(extracted, ClientConfig(country_code="SK"))

    e02 = [i for i in report.issues if i.code == "E02"]
    assert e02 and e02[0].severity == "warning"
    # E02 alone must not invalidate — only gross is mandatory for approval.
    assert all(i.code != "E03" for i in report.issues)


def test_e03_fires_on_net_plus_tax_mismatch():
    extracted = _full(total_amount=ConfidenceValue(value=121.0, confidence=0.95))
    report = validate_invoice(extracted, ClientConfig(country_code="SK"))

    e03 = [i for i in report.issues if i.code == "E03"]
    assert e03 and e03[0].severity == "error"
    assert report.valid is False


def test_e03_passes_with_float_artifacts_via_round_first():
    # 0.1 + 0.2 == 0.30000000000000004 in float; round-first must treat it as equal.
    extracted = _full(
        subtotal=ConfidenceValue(value=0.1, confidence=0.95),
        vat_amount=ConfidenceValue(value=0.2, confidence=0.95),
        total_amount=ConfidenceValue(value=0.3, confidence=0.95),
    )
    report = validate_invoice(extracted, ClientConfig(country_code="SK"))

    assert all(i.code != "E03" for i in report.issues)


def test_e03_not_emitted_when_components_missing():
    extracted = _full(subtotal=ConfidenceValue(value=None, confidence=0.0))
    report = validate_invoice(extracted, ClientConfig(country_code="SK"))

    assert "E02" in _codes(report)
    assert "E03" not in _codes(report)


def test_bool_total_is_not_treated_as_number():
    # A stray boolean must trigger E02 (incomplete), never arithmetic.
    extracted = _full(total_amount=ConfidenceValue(value=True, confidence=0.95))
    report = validate_invoice(extracted, ClientConfig(country_code="SK"))

    assert "E02" in _codes(report)
    assert "E03" not in _codes(report)


def test_e04_when_supplier_vat_missing_in_vat_country():
    extracted = _full(vendor_vat=ConfidenceValue(value=None, confidence=0.0))
    report = validate_invoice(extracted, ClientConfig(country_code="SK"))

    e04 = [i for i in report.issues if i.code == "E04"]
    assert e04 and e04[0].severity == "warning"
    assert report.valid is True  # warning only


def test_e05_only_fires_when_recipient_partially_present():
    no_recipient = validate_invoice(_full(), ClientConfig(country_code="SK"))
    assert "E05" not in _codes(no_recipient)

    partial = validate_invoice(
        _full(recipient_name=ConfidenceValue(value="Buyer s.r.o.", confidence=0.9)),
        ClientConfig(country_code="SK"),
    )
    e05 = [i for i in partial.issues if i.code == "E05"]
    assert e05 and e05[0].severity == "warning"


def test_required_loop_skips_non_scalar_field_without_crashing():
    # line_items is a list, not a ConfidenceValue — a misconfigured required list
    # must be skipped, not raise AttributeError.
    config = ClientConfig(fields_required=["vendor_name", "line_items"])
    report = validate_invoice(_full(), config)
    assert isinstance(report.issues, list)


def test_tax_lines_sum_mismatch_emits_e02_warning():
    from app.models import TaxLine
    # tax_lines sum to 25, but vat_amount = 20 → mismatch.
    extracted = _full(
        vat_amount=ConfidenceValue(value=20.0, confidence=0.95),
        tax_lines=[TaxLine(rate=0.25, base=100.0, amount=25.0)],
    )
    report = validate_invoice(extracted, ClientConfig(country_code="SK"))
    e02 = [i for i in report.issues if i.code == "E02"]
    assert e02 and e02[0].severity == "warning"


def test_tax_lines_sum_matches_no_extra_e02():
    from app.models import TaxLine
    # tax_lines sum to 20, matches vat_amount = 20 → no extra E02.
    extracted = _full(
        vat_amount=ConfidenceValue(value=20.0, confidence=0.95),
        tax_lines=[TaxLine(rate=0.20, base=100.0, amount=20.0)],
    )
    report = validate_invoice(extracted, ClientConfig(country_code="SK"))
    e02_tax_line = [i for i in report.issues if i.code == "E02" and "Tax lines" in i.message]
    assert not e02_tax_line
