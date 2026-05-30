"""Gemini-based invoice field extractor.

Uses Google's Gemini API with structured output (Pydantic schema) to extract
invoice fields from raw PDF text. Returns the same `ExtractedInvoice` shape as
the regex extractor, so the pipeline can swap them transparently.
"""
from __future__ import annotations

import json
from typing import Protocol

from app.models import ConfidenceValue, ExtractedInvoice, LineItem


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
        "due_date": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "subtotal": {"type": "object", "properties": {"value": {"type": "number", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "vat_amount": {"type": "object", "properties": {"value": {"type": "number", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "total_amount": {"type": "object", "properties": {"value": {"type": "number", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "currency": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "po_number": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
        "cost_center": {"type": "object", "properties": {"value": {"type": "string", "nullable": True}, "confidence": {"type": "number"}}, "required": ["value", "confidence"]},
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
    },
    "required": [
        "vendor_name", "vendor_ico", "vendor_vat", "vendor_iban", "invoice_number",
        "invoice_date", "due_date", "subtotal", "vat_amount", "total_amount",
        "currency", "po_number", "cost_center", "line_items",
    ],
}


PROMPT = """You extract structured fields from an invoice. The text below was
extracted from a PDF (so layout may be lost). Return JSON matching the schema.

Rules:
- For every field set "value" (string/number) and "confidence" (0.0-1.0).
- If a field is missing from the text, set value to null and confidence to 0.0.
- Dates use the format found in the document (e.g. DD.MM.YYYY for Slovak invoices).
- Amounts are numbers, not strings. Use a dot as decimal separator.
- vendor_ico is the company registration number (IČO/IČ — typically 6-8 digits, NOT the VAT number).
- vendor_vat is the VAT/tax ID (IČ DPH / DIČ — Slovak format: SK + 10 digits).
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

    return ExtractedInvoice(
        vendor_name=cv("vendor_name"),
        vendor_ico=cv("vendor_ico"),
        vendor_vat=cv("vendor_vat"),
        vendor_iban=cv("vendor_iban"),
        invoice_number=cv("invoice_number"),
        invoice_date=cv("invoice_date"),
        due_date=cv("due_date"),
        subtotal=cv("subtotal"),
        vat_amount=cv("vat_amount"),
        total_amount=cv("total_amount"),
        currency=cv("currency"),
        po_number=cv("po_number"),
        cost_center=cv("cost_center"),
        line_items=line_items,
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
