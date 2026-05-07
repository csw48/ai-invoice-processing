from app.models import ClientConfig, EnrichedInvoice
from app.services.extract import extract_invoice_fields
from app.services.formatters import format_invoice
from app.services.pipeline import process_invoice
from app.services.validate import validate_invoice

SAMPLE_INVOICE = """Firma Test s.r.o.
VAT: SK1234567890
IBAN: SK3112000000198742637541
Invoice number: INV-2026-001
Invoice date: 07.05.2026
Due date: 21.05.2026
Subtotal: 100.00
VAT: 20.00
Total: 120.00 EUR
"""


def test_extract_invoice_fields_from_common_invoice_text():
    extracted = extract_invoice_fields(SAMPLE_INVOICE)

    assert extracted.vendor_name.value == "Firma Test s.r.o."
    assert extracted.vendor_vat.value == "SK1234567890"
    assert extracted.invoice_number.value == "INV-2026-001"
    assert extracted.total_amount.value == 120.00


def test_validate_invoice_flags_missing_required_fields():
    extracted = extract_invoice_fields("Unknown vendor only")
    report = validate_invoice(extracted, ClientConfig())

    assert report.valid is False
    assert {issue.field for issue in report.issues if issue.severity == "error"} >= {
        "invoice_number",
        "invoice_date",
        "total_amount",
    }


def test_validate_invoice_detects_vat_math_error():
    extracted = extract_invoice_fields(SAMPLE_INVOICE.replace("Total: 120.00", "Total: 121.00"))
    report = validate_invoice(extracted, ClientConfig())

    assert report.valid is False
    assert any(issue.field == "total_amount" for issue in report.issues)


def test_format_invoice_as_csv_and_pohoda_xml():
    extracted = extract_invoice_fields(SAMPLE_INVOICE)
    enriched = EnrichedInvoice(extracted=extracted)

    csv_payload = format_invoice(enriched, "csv")
    xml_payload = format_invoice(enriched, "pohoda")

    assert csv_payload["type"] == "csv"
    assert "INV-2026-001" in csv_payload["payload"]
    assert xml_payload["type"] == "pohoda"
    assert "INV-2026-001" in xml_payload["payload"]


def test_process_invoice_returns_review_ready_payload():
    result = process_invoice(SAMPLE_INVOICE, ClientConfig(output_connector="json"))

    assert result.status == "review"
    assert result.validation.valid is True
    assert result.formatted["type"] == "json"
