"""Gemini-based invoice field extractor.

Uses Google's Gemini API with structured output (Pydantic schema) to extract
invoice fields from raw PDF text. Returns the same `ExtractedInvoice` shape as
the regex extractor, so the pipeline can swap them transparently.
"""
from __future__ import annotations

import json
from typing import Protocol

from app.models import ConfidenceValue, ExtractedInvoice, LineItem, TaxLine
from app.services.normalize import normalize_number


# Schema for structured output. We keep it simple and JSON-serialisable: a flat
# dict of field -> {value, confidence} plus a list of line items.
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor_name": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "vendor_ico": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "vendor_vat": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "vendor_iban": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "invoice_number": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "invoice_date": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "delivered_at": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "due_date": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "subtotal": {"type": "object", "properties": {"value": {"type": "number", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "vat_amount": {"type": "object", "properties": {"value": {"type": "number", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "total_amount": {"type": "object", "properties": {"value": {"type": "number", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "currency": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "po_number": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "cost_center": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "recipient_name": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "recipient_vat": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "recipient_address": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "recipient_postcode": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "recipient_city": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "recipient_country": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "qty": {"type": "number"},
                    "unit_price": {"type": "number"},
                    "vat_rate": {"type": "number"},
                    "total": {"type": "number"},
                },
                "required": ["description", "qty", "unit_price", "vat_rate", "total"],
            },
        },
        "tax_lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rate": {"type": "number"},
                    "base": {"type": "number"},
                    "amount": {"type": "number"},
                },
                "required": ["rate", "base", "amount"],
            },
        },
        "amount_due": {"type": "object", "properties": {"value": {"type": "number", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
    },
    "required": [
        "vendor_name", "vendor_ico", "vendor_vat", "vendor_iban", "invoice_number",
        "invoice_date", "delivered_at", "due_date", "subtotal", "vat_amount", "total_amount",
        "currency", "po_number", "cost_center",
        "recipient_name", "recipient_vat", "recipient_address",
        "recipient_postcode", "recipient_city", "recipient_country",
        "line_items", "tax_lines", "amount_due",
    ],
}


PROMPT = """You extract structured fields from an invoice. The text below was
extracted from a PDF (so layout may be lost). Return JSON matching the schema.

Rules:
- For every field set "value" (string/number) and "confidence" (0.0-1.0).
- If a field is missing from the text, set value to null and confidence to 0.0.
- Dates use the format found in the document (e.g. DD.MM.YYYY for Slovak invoices).
- delivered_at is the service/delivery date (dátum dodania / Leistungsdatum / Lieferdatum / date of supply). If the document does not state one, leave it null — the pipeline falls back to invoice_date.
- Amounts are numbers, not strings. Use a dot as decimal separator.
- vendor_ico is the company registration number (IČO/IČ — typically 6-8 digits, NOT the VAT number).
- vendor_vat is the VAT/tax ID (IČ DPH / DIČ — Slovak format: SK + 10 digits).
- recipient_* describes the BUYER (odberateľ/customer) the invoice is addressed to — a DIFFERENT entity from the vendor. Take it from where a company name and full postal address appear together; never from the footer and never from the party that holds the bank/IBAN details (that is the vendor). Split the address block into recipient_address (street), recipient_postcode, recipient_city; recipient_country as ISO ALPHA-2 (SK, DE, AT).
- tax_lines is an array of VAT band breakdowns. Include one entry per distinct VAT rate on the invoice, with rate (decimal, e.g. 0.23 for 23%), base (net amount for that band), and amount (tax amount for that band). Leave empty if no breakdown is visible.
- amount_due is the actual amount owed — equals total_amount unless a prepayment or credit reduces what is outstanding.
- Be conservative with confidence: 0.9+ only if the field is explicit and unambiguous.

Invoice text:
---
{raw_text}
---
"""


class _GeminiClient(Protocol):
    """Subset of the google-genai client surface we use, so tests can stub it."""

    def generate_invoice_json(self, model: str, prompt: str, schema: dict) -> str:
        ...


def parse_gemini_response(payload: str) -> ExtractedInvoice:
    """Parse a Gemini JSON response into an ExtractedInvoice. Public for testing."""
    data = json.loads(payload)

    def cv(key: str) -> ConfidenceValue:
        item = data.get(key) or {}
        return ConfidenceValue(value=item.get("value"), confidence=float(item.get("confidence") or 0.0))

    def cv_number(key: str) -> ConfidenceValue:
        # Apply the brief's 16-char document-number normalization (left-trim + '*').
        base = cv(key)
        return base.model_copy(update={"value": normalize_number(base.value)})

    line_items = [
        LineItem(
            description=str(li.get("description", "")),
            qty=float(li.get("qty") or 0),
            unit_price=float(li.get("unit_price") or 0),
            vat_rate=float(li.get("vat_rate") or 0),
            total=float(li.get("total") or 0),
        )
        for li in (data.get("line_items") or [])
    ]

    tax_lines = [
        TaxLine(
            rate=float(tl.get("rate") or 0),
            base=float(tl.get("base") or 0),
            amount=float(tl.get("amount") or 0),
        )
        for tl in (data.get("tax_lines") or [])
    ]

    return ExtractedInvoice(
        vendor_name=cv("vendor_name"),
        vendor_ico=cv("vendor_ico"),
        vendor_vat=cv("vendor_vat"),
        vendor_iban=cv("vendor_iban"),
        invoice_number=cv_number("invoice_number"),
        invoice_date=cv("invoice_date"),
        delivered_at=cv("delivered_at"),
        due_date=cv("due_date"),
        subtotal=cv("subtotal"),
        vat_amount=cv("vat_amount"),
        total_amount=cv("total_amount"),
        currency=cv("currency"),
        po_number=cv("po_number"),
        cost_center=cv("cost_center"),
        recipient_name=cv("recipient_name"),
        recipient_vat=cv("recipient_vat"),
        recipient_address=cv("recipient_address"),
        recipient_postcode=cv("recipient_postcode"),
        recipient_city=cv("recipient_city"),
        recipient_country=cv("recipient_country"),
        line_items=line_items,
        tax_lines=tax_lines,
        amount_due=cv("amount_due"),
    )


class GeminiExtractor:
    """Calls Gemini with structured output and returns an ExtractedInvoice.

    Tries each model in `models` in order. If a call fails (e.g. 503 UNAVAILABLE
    because a preview model is overloaded), the next model is tried.
    """

    def __init__(
        self,
        client: _GeminiClient,
        model: str = "gemini-3.1-flash-lite-preview",
        fallback_models: list[str] | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._fallback_models = fallback_models or ["gemini-2.5-flash-lite"]

    def extract(self, raw_text: str) -> ExtractedInvoice:
        prompt = PROMPT.format(raw_text=raw_text)
        last_error: Exception | None = None
        for model in [self._model, *self._fallback_models]:
            try:
                payload = self._client.generate_invoice_json(model, prompt, EXTRACTION_SCHEMA)
                return parse_gemini_response(payload)
            except Exception as exc:  # noqa: BLE001 - we want to fall through any provider error
                last_error = exc
        assert last_error is not None
        raise last_error


class RealGeminiClient:
    """Thin wrapper around google-genai. Not exercised in CI tests."""

    def __init__(self, api_key: str) -> None:
        from google import genai
        self._genai = genai
        self._client = genai.Client(api_key=api_key)

    def generate_invoice_json(self, model: str, prompt: str, schema: dict) -> str:
        from google.genai import types

        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.0,
            ),
        )
        return response.text or "{}"
