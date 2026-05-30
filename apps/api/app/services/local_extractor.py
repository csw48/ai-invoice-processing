"""Local LLM invoice extractor via OpenAI-compatible API (LM Studio / Ollama).

Connects to any OpenAI-compatible endpoint. Default: LM Studio at
http://localhost:1234/v1. Override with LOCAL_LLM_URL and LOCAL_LLM_MODEL
environment variables.

Reuses parse_gemini_response for JSON → ExtractedInvoice parsing since the
output schema is identical.
"""
from __future__ import annotations

from app.models import ExtractedInvoice
from app.services.gemini_extractor import parse_gemini_response

PROMPT = """Extract invoice fields. Return ONLY this JSON (no markdown, no explanation):

{{"vendor_name":{{"value":"<supplier company name>","confidence":0.0}},
"vendor_ico":{{"value":"<IČO/company reg number>","confidence":0.0}},
"vendor_vat":{{"value":"<IČ DPH/VAT ID>","confidence":0.0}},
"vendor_iban":{{"value":"<IBAN>","confidence":0.0}},
"invoice_number":{{"value":"<invoice number>","confidence":0.0}},
"invoice_date":{{"value":"<issue date>","confidence":0.0}},
"due_date":{{"value":"<due date>","confidence":0.0}},
"subtotal":{{"value":0.0,"confidence":0.0}},
"vat_amount":{{"value":0.0,"confidence":0.0}},
"total_amount":{{"value":0.0,"confidence":0.0}},
"currency":{{"value":"EUR","confidence":0.0}},
"po_number":{{"value":null,"confidence":0.0}},
"cost_center":{{"value":null,"confidence":0.0}},
"line_items":[{{"description":"<item name>","qty":1.0,"unit_price":0.0,"vat_rate":0.0,"total":0.0}}]}}

Rules:
- vendor_name = supplier/dodavatel company name (NOT IČO/DIČ labels).
- vendor_ico = company registration number (IČO/IČ) — 6-8 digit number. NOT the VAT number.
- vendor_vat = VAT/tax ID (IČ DPH/DIČ) — Slovak: SK + 10 digits. Different from IČO.
- invoice_date: look for "Dátum vystavenia","Datum vystavení","Ausstellungsdatum","Date","Issue date".
- due_date: look for "Dátum splatnosti","Datum splatnosti","Fälligkeitsdatum","Due date".
- vat_amount = VAT money amount (e.g. 27.94), NOT the rate (e.g. 23%).
- total_amount = final total due (SPOLU/Celkem/Total/Gesamtbetrag).
- line_items: extract each purchased item/service with its qty, unit price, vat rate (as decimal e.g. 0.23), and line total.
- Amounts: comma decimal "149,44" → 149.44. Thousands sep "1.234,56" → 1234.56.
- Missing fields: null value, 0.0 confidence. Empty line_items: [].
- Dates: keep format as-is (e.g. "11. 04. 2026").
- confidence: 0.95 if explicit, 0.7 if inferred, 0.0 if missing.

Invoice text:
---
{raw_text}
---
"""


class LocalLLMExtractor:
    """Calls a local OpenAI-compatible LLM and returns an ExtractedInvoice."""

    def __init__(self, base_url: str, model: str, api_key: str = "lm-studio") -> None:  # noqa: S107
        from openai import OpenAI
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self._model = model

    def extract(self, raw_text: str) -> ExtractedInvoice:
        prompt = PROMPT.format(raw_text=raw_text)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=2048,
        )
        raw = response.choices[0].message.content or "{}"
        payload = _extract_json(raw)
        return parse_gemini_response(payload)


def _extract_json(text: str) -> str:
    """Pull the first JSON object out of a response that may contain markdown fences."""
    import re
    # strip ```json ... ``` or ``` ... ``` fences
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    # find raw {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text
