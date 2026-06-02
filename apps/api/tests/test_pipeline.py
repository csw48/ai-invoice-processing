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


def test_extract_line_items_from_multiline_czech_slovak_table():
    raw_text = """ALMA OBCHOD s.r.o.
Faktúra EU2026-00439
DPH
CENA ZA MJ
CELKOM BEZ DPH
1
ks
Rastúca posteľ Montessori Tobi biela 90x200 cm + rošt
ZADARMO
23 %
€ 107,67
€ 107,67
1
ks
doprava
23 %
€ 13,83
€ 13,83
SADZBA
ZÁKLAD
DPH
23 %
€ 121,50
€ 27,94
€ 149,44
"""

    extracted = extract_invoice_fields(raw_text)

    assert len(extracted.line_items) == 2
    assert extracted.line_items[0].description == "Rastúca posteľ Montessori Tobi biela 90x200 cm + rošt"
    assert extracted.line_items[0].qty == 1
    assert extracted.line_items[0].unit_price == 107.67
    assert extracted.line_items[0].vat_rate == 0.23
    assert extracted.line_items[0].total == 107.67
    assert extracted.line_items[1].description == "doprava"
    assert extracted.line_items[1].unit_price == 13.83


def test_extract_captures_negative_totals_for_credit_notes():
    text = (
        "Dobropis s.r.o.\n"
        "Invoice number: CN-2026-001\n"
        "Subtotal: -100.00\n"
        "VAT: -20.00\n"
        "Total: -120.00 EUR\n"
    )
    extracted = extract_invoice_fields(text)
    assert extracted.subtotal.value == -100.0
    assert extracted.vat_amount.value == -20.0
    assert extracted.total_amount.value == -120.0


def test_delivered_at_extracted_when_present():
    text = SAMPLE_INVOICE + "Date of supply: 05.05.2026\n"
    extracted = extract_invoice_fields(text)
    assert extracted.delivered_at.value == "05.05.2026"


def test_delivered_at_falls_back_to_invoice_date():
    from app.services.extract import fill_delivered_at

    extracted = extract_invoice_fields(SAMPLE_INVOICE)
    assert extracted.delivered_at.value is None  # not stated in SAMPLE
    filled = fill_delivered_at(extracted)
    assert filled.delivered_at.value == filled.invoice_date.value == "07.05.2026"
    # The fallback is a defined rule, so it inherits the issue-date confidence.
    assert filled.delivered_at.confidence == filled.invoice_date.confidence


def test_pipeline_fills_delivered_at_via_fallback():
    result = process_invoice(SAMPLE_INVOICE, ClientConfig(output_connector="json"), "default")
    assert result.extracted.delivered_at.value == "07.05.2026"


def test_amount_parses_eu_and_us_thousands_separators():
    from app.services.extract import _amount

    assert _amount("107,67") == 107.67          # EU comma decimal
    assert _amount("1.234,56") == 1234.56        # EU dot thousands
    assert _amount("1 234,56") == 1234.56        # EU space thousands
    assert _amount("1,234.56") == 1234.56        # US comma thousands (was misparsed)
    assert _amount("100.00") == 100.0            # plain dot decimal


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
    # Default document_type is an ordinary received invoice.
    assert xml_payload["document_type"] == "invoice"
    assert "receivedInvoice" in xml_payload["payload"]
    assert "Prijatá faktúra" in xml_payload["payload"]
    # No recipient extracted → no myIdentity block emitted.
    assert "myIdentity" not in xml_payload["payload"]


def test_format_credit_note_uses_pohoda_credit_notice_type():
    extracted = extract_invoice_fields(SAMPLE_INVOICE)
    enriched = EnrichedInvoice(extracted=extracted)

    xml_payload = format_invoice(enriched, "pohoda", "credit_note")
    json_payload = format_invoice(enriched, "json", "credit_note")

    assert xml_payload["document_type"] == "credit_note"
    assert "receivedCreditNotice" in xml_payload["payload"]
    assert "receivedInvoice" not in xml_payload["payload"]
    assert "Dobropis" in xml_payload["payload"]
    # Consumers of other connectors can still distinguish the type.
    assert json_payload["document_type"] == "credit_note"


def test_pohoda_emits_my_identity_when_recipient_present():
    from app.models import ConfidenceValue

    extracted = extract_invoice_fields(SAMPLE_INVOICE)
    extracted.recipient_name = ConfidenceValue(value="Odberateľ s.r.o.", confidence=0.9)
    extracted.recipient_vat = ConfidenceValue(value="SK9876543210", confidence=0.9)
    extracted.recipient_city = ConfidenceValue(value="Bratislava", confidence=0.9)
    enriched = EnrichedInvoice(extracted=extracted)

    xml = format_invoice(enriched, "pohoda")["payload"]

    assert "inv:myIdentity" in xml
    assert "Odberateľ s.r.o." in xml
    assert "SK9876543210" in xml
    assert "Bratislava" in xml


def test_pohoda_emits_line_items_and_vat_bands():
    from app.models import LineItem

    extracted = extract_invoice_fields(SAMPLE_INVOICE)
    extracted.line_items = [
        LineItem(description="Standard goods", qty=1, unit_price=100.0, vat_rate=0.23, total=100.0),
        LineItem(description="Reduced goods", qty=1, unit_price=50.0, vat_rate=0.10, total=50.0),
        LineItem(description="Exempt service", qty=1, unit_price=10.0, vat_rate=0.0, total=10.0),
    ]
    enriched = EnrichedInvoice(extracted=extracted)

    xml = format_invoice(enriched, "pohoda")["payload"]

    # Detail block with one item per line.
    assert "inv:invoiceDetail" in xml
    assert xml.count("inv:invoiceItem") == 2 * 3  # open + close tags per item
    assert "Standard goods" in xml and "Reduced goods" in xml and "Exempt service" in xml
    # Highest rate (23%) -> high band, 10% -> low band, 0% -> none band.
    assert "<inv:rateVAT>high</inv:rateVAT>" in xml
    assert "<inv:rateVAT>low</inv:rateVAT>" in xml
    assert "<inv:rateVAT>none</inv:rateVAT>" in xml
    # Summary carries all three bands; high VAT = 100*0.23 = 23.00.
    assert "typ:priceHigh" in xml and "<typ:priceHighVAT>23.00</typ:priceHighVAT>" in xml
    assert "typ:priceLow" in xml and "<typ:priceLowVAT>5.00</typ:priceLowVAT>" in xml
    assert "typ:priceNone" in xml


def test_pohoda_falls_back_to_flat_totals_without_line_items():
    # SAMPLE_INVOICE is summary-only text (no parseable item table).
    extracted = extract_invoice_fields(SAMPLE_INVOICE)
    assert extracted.line_items == []
    xml = format_invoice(EnrichedInvoice(extracted=extracted), "pohoda")["payload"]

    assert "inv:invoiceDetail" not in xml
    assert "typ:priceHigh" in xml  # flat fallback still emits the standard band


def test_csv_carries_richer_column_set():
    extracted = extract_invoice_fields(SAMPLE_INVOICE)
    csv_payload = format_invoice(EnrichedInvoice(extracted=extracted), "csv")["payload"]

    header = csv_payload.splitlines()[0]
    for col in ("vendor_vat", "vendor_iban", "subtotal", "vat_amount", "due_date", "recipient_name"):
        assert col in header
    assert "SK1234567890" in csv_payload  # vendor_vat value now present


def test_process_invoice_returns_review_ready_payload():
    result = process_invoice(SAMPLE_INVOICE, ClientConfig(output_connector="json"), "default")

    assert result.status == "review"
    assert result.validation.valid is True
    assert result.formatted["type"] == "json"


def test_process_invoice_repairs_zero_line_items_from_extractor():
    raw_text = """ALMA OBCHOD s.r.o.
Faktúra EU2026-00439
Invoice date: 11.04.2026
Total: 149.44 EUR
1
ks
Rastúca posteľ Montessori Tobi biela 90x200 cm + rošt
23 %
€ 107,67
€ 107,67
"""

    def weak_extractor(text: str):
        extracted = extract_invoice_fields(text)
        extracted.line_items[0].qty = 0
        extracted.line_items[0].unit_price = 0
        extracted.line_items[0].total = 0
        return extracted

    result = process_invoice(raw_text, ClientConfig(output_connector="json"), "default", extractor=weak_extractor)

    assert result.extracted.line_items[0].qty == 1
    assert result.extracted.line_items[0].unit_price == 107.67
    assert result.formatted["payload"]["line_items"][0]["total"] == 107.67


def test_process_invoice_falls_back_when_configured_extractor_fails():
    def failing_extractor(text: str):
        raise RuntimeError("local model unavailable")

    result = process_invoice(SAMPLE_INVOICE, ClientConfig(output_connector="json"), "default", extractor=failing_extractor)

    assert result.extracted.invoice_number.value == "INV-2026-001"
    assert result.validation.valid is True
