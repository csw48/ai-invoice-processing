import json

from app.models import Classification, ClientConfig, DocumentType, InvoiceStatus
from app.services.classify import (
    GeminiClassifier,
    classify_document,
    parse_classification_response,
)
from app.services.pipeline import process_invoice

INVOICE_TEXT = """Firma Test s.r.o.
VAT: SK1234567890
IBAN: SK3112000000198742637541
Invoice number: INV-2026-001
Subtotal: 100.00
VAT: 20.00
Total: 120.00 EUR
"""

CREDIT_NOTE_TEXT = """ALMA OBCHOD s.r.o.
Dobropis č. DOB-2026-7
IBAN: SK3112000000198742637541
Total: 120.00 EUR
"""


def test_classify_invoice():
    result = classify_document(INVOICE_TEXT)
    assert result.document_type is DocumentType.invoice


def test_classify_credit_note_by_marker():
    result = classify_document(CREDIT_NOTE_TEXT)
    assert result.document_type is DocumentType.credit_note


def test_classify_junk_when_no_markers_or_money():
    result = classify_document("hello there, hope you are well\nsee you soon")
    assert result.document_type is DocumentType.junk


def test_parse_classification_response():
    payload = json.dumps({
        "documentType": "invoice",
        "typeReasoning": "has net amount and two parties",
        "sender": {"companyName": "Acme GmbH", "address": "Berlin", "vatId": "DE123456789"},
        "recipient": {"companyName": "Buyer s.r.o.", "address": "Bratislava", "vatId": None},
    })
    result = parse_classification_response(payload)
    assert result.document_type is DocumentType.invoice
    assert result.sender.company_name == "Acme GmbH"
    assert result.recipient.company_name == "Buyer s.r.o."


def test_parse_classification_unknown_type_falls_back_to_other():
    payload = json.dumps({"documentType": "purchase_order", "typeReasoning": "x", "sender": {}, "recipient": {}})
    assert parse_classification_response(payload).document_type is DocumentType.other


class _StubClient:
    def __init__(self, payload: str):
        self._payload = payload

    def generate_invoice_json(self, model, prompt, schema):
        return self._payload


def test_gemini_classifier_uses_client():
    payload = json.dumps({"documentType": "junk", "typeReasoning": "blank", "sender": {}, "recipient": {}})
    classifier = GeminiClassifier(client=_StubClient(payload))
    assert classifier.classify("whatever").document_type is DocumentType.junk


def test_pipeline_short_circuits_junk():
    config = ClientConfig()

    def boom_extractor(_raw):
        raise AssertionError("extractor must not run for junk")

    result = process_invoice(
        raw_text="random noise",
        config=config,
        client_id="c1",
        extractor=boom_extractor,
        classifier=lambda _t: Classification(document_type=DocumentType.junk),
    )
    assert result.status is InvoiceStatus.discarded
    assert result.classification.document_type is DocumentType.junk
    assert result.extracted.vendor_name.value is None


def test_pipeline_redirects_other():
    result = process_invoice(
        raw_text="some doc",
        config=ClientConfig(),
        client_id="c1",
        classifier=lambda _t: Classification(document_type=DocumentType.other),
    )
    assert result.status is InvoiceStatus.redirect
    assert result.formatted["type"] == "skipped"


def test_pipeline_runs_extraction_for_invoice():
    result = process_invoice(
        raw_text=INVOICE_TEXT,
        config=ClientConfig(),
        client_id="c1",
        classifier=lambda _t: Classification(document_type=DocumentType.invoice),
    )
    assert result.status is InvoiceStatus.review
    assert result.classification.document_type is DocumentType.invoice
    assert result.extracted.vendor_vat.value == "SK1234567890"


def test_pipeline_threads_credit_note_into_formatted_output():
    result = process_invoice(
        raw_text=INVOICE_TEXT,
        config=ClientConfig(output_connector="pohoda"),
        client_id="c1",
        classifier=lambda _t: Classification(document_type=DocumentType.credit_note),
    )
    assert result.classification.document_type is DocumentType.credit_note
    assert result.formatted["document_type"] == "credit_note"
    assert "receivedCreditNotice" in result.formatted["payload"]


def test_pipeline_classifier_failure_falls_back_to_deterministic():
    def failing_classifier(_t):
        raise RuntimeError("LLM down")

    result = process_invoice(
        raw_text=INVOICE_TEXT,
        config=ClientConfig(),
        client_id="c1",
        classifier=failing_classifier,
    )
    # deterministic fallback classifies the sample as an invoice and proceeds
    assert result.classification.document_type is DocumentType.invoice
    assert result.extracted.vendor_vat.value == "SK1234567890"
