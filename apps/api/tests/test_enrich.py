"""Unit tests for the enrich step (vendor matching + duplicate detection)."""
from app.models import ConfidenceValue, ExtractedInvoice, VendorCreate
from app.repositories import InMemoryInvoiceRepository, InMemoryVendorRepository
from app.services.enrich import enrich_invoice


CLIENT = "client-a"


def _extracted(**overrides) -> ExtractedInvoice:
    base = dict(
        vendor_name=ConfidenceValue(value="ACME s.r.o.", confidence=0.95),
        vendor_vat=ConfidenceValue(value="SK1234567890", confidence=0.95),
        invoice_number=ConfidenceValue(value="INV-1", confidence=0.95),
    )
    base.update(overrides)
    return ExtractedInvoice(**base)


def test_no_vendor_repo_is_noop():
    result = enrich_invoice(_extracted(), None, None, CLIENT)
    assert result.vendor_metadata == {}
    assert result.duplicate is False


def test_matches_vendor_by_vat_and_pulls_metadata():
    vendors = InMemoryVendorRepository()
    vendors.create(
        VendorCreate(name="ACME s.r.o.", vat_number="SK1234567890", iban="SK99", category="supplies"),
        CLIENT,
    )
    result = enrich_invoice(_extracted(), vendors, None, CLIENT)

    assert result.category == "supplies"
    assert result.vendor_metadata["iban"] == "SK99"


def test_vat_match_is_tenant_scoped():
    vendors = InMemoryVendorRepository()
    vendors.create(VendorCreate(name="ACME", vat_number="SK1234567890"), "other-tenant")
    result = enrich_invoice(_extracted(), vendors, None, CLIENT)

    assert result.vendor_metadata == {}


def test_falls_back_to_name_when_vat_absent():
    vendors = InMemoryVendorRepository()
    vendors.create(VendorCreate(name="ACME s.r.o.", category="supplies"), CLIENT)
    result = enrich_invoice(
        _extracted(vendor_vat=ConfidenceValue(value=None, confidence=0.0)),
        vendors,
        None,
        CLIENT,
    )
    assert result.category == "supplies"


def test_find_by_name_matches_exact_and_prefix_not_arbitrary_substring():
    vendors = InMemoryVendorRepository()
    vendors.create(VendorCreate(name="ACME s.r.o.", category="supplies"), CLIENT)

    # Exact and prefix match.
    assert vendors.find_by_name("ACME s.r.o.", CLIENT) is not None
    assert vendors.find_by_name("ACME", CLIENT) is not None
    # Bare legal-form substring must not match a random vendor.
    assert vendors.find_by_name("s.r.o.", CLIENT) is None
    # Empty / too-short query must not match.
    assert vendors.find_by_name("", CLIENT) is None
    assert vendors.find_by_name("  ", CLIENT) is None


def test_duplicate_detected_within_tenant():
    invoices = InMemoryInvoiceRepository()
    vendors = InMemoryVendorRepository()
    # First invoice persisted as a prior record.
    from app.services.pipeline import process_invoice
    from app.models import ClientConfig

    first = process_invoice(
        "ACME s.r.o.\nVAT: SK1234567890\nInvoice number: INV-1\nTotal: 10.00 EUR",
        ClientConfig(output_connector="json"),
        CLIENT,
    )
    invoices.save(first, file_path="m://x", raw_text="x", client_id=CLIENT)

    result = enrich_invoice(_extracted(), vendors, invoices, CLIENT)
    assert result.duplicate is True


def test_no_false_duplicate_when_keys_missing():
    invoices = InMemoryInvoiceRepository()
    vendors = InMemoryVendorRepository()
    blank = _extracted(
        vendor_vat=ConfidenceValue(value=None, confidence=0.0),
        invoice_number=ConfidenceValue(value=None, confidence=0.0),
    )
    result = enrich_invoice(blank, vendors, invoices, CLIENT)
    assert result.duplicate is False
