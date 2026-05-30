"""Document classification — Step 1 of the pipeline.

Runs BEFORE extraction so that junk / non-invoice documents skip the expensive
LLM extraction step (conditional execution = cost saving).

Two implementations, same `(raw_text: str) -> Classification` signature:
  * `classify_document` — deterministic heuristics, always available, used as the
    default and as the fallback when an LLM call fails (mirrors the extractor pattern).
  * `GeminiClassifier` — LLM classification following the brief's heuristics
    (context over title, footer = sender, address-block = recipient, overrides).
"""
from __future__ import annotations

import json
import re
from typing import Protocol

from app.models import Classification, DocumentType, Party


# --- deterministic classifier -------------------------------------------------

_VAT_RE = re.compile(r"\b([A-Z]{2}\d{8,12})\b")
_MONEY_RE = re.compile(r"(?:€|EUR|\$|£|Kč|CZK)\s*-?\d|[-\d][\d .]*[,.]\d{2}\s*(?:€|EUR|\$|£|Kč|CZK)?", re.I)
_NEGATIVE_TOTAL_RE = re.compile(r"(?:total|spolu|celkom|celkem|gesamt|amount due)\D*-\s*[\d.,]+", re.I)

_CREDIT_NOTE_MARKERS = ("dobropis", "credit note", "creditnote", "gutschrift", "kreditná nota", "kreditni nota")
_INVOICE_MARKERS = ("invoice", "faktúra", "faktura", "rechnung", "tax invoice", "ič dph", "vat")


def _has_money(text: str) -> bool:
    return _MONEY_RE.search(text) is not None


def _looks_negative(text: str) -> bool:
    return _NEGATIVE_TOTAL_RE.search(text) is not None


def _guess_party(lines: list[str], text: str) -> Party:
    company = lines[0] if lines else None
    vat_match = _VAT_RE.search(text)
    return Party(company_name=company, vat_id=vat_match.group(1) if vat_match else None)


def classify_document(raw_text: str) -> Classification:
    """Deterministic classifier — the always-on default and the LLM fallback.

    Distinguishing `invoice` from `other` reliably needs document layout, which the
    LLM classifier has and this one does not. So this fallback is deliberately
    LENIENT: the costs are asymmetric — wrongly discarding a real invoice loses
    data, while wrongly accepting one only wastes a cheap extraction pass. It
    therefore only diverts to `junk` (clearly empty / no invoice markers) or
    `credit_note` (explicit marker or negative payable), and otherwise defaults to
    `invoice`.
    """
    text = raw_text or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    lower = text.lower()
    sender = _guess_party(lines, text)

    # junk: almost no content, or no monetary value AND no invoice-like markers
    if len(lower.strip()) < 40 or (not _has_money(text) and not any(m in lower for m in _INVOICE_MARKERS)):
        return Classification(document_type=DocumentType.junk, type_reasoning="No invoice markers or monetary amounts")

    if any(m in lower for m in _CREDIT_NOTE_MARKERS) or _looks_negative(text):
        return Classification(
            document_type=DocumentType.credit_note,
            type_reasoning="Credit-note marker or negative payable amount detected",
            sender=sender,
        )

    return Classification(
        document_type=DocumentType.invoice,
        type_reasoning="Invoice markers present (deterministic default)",
        sender=sender,
    )


# --- LLM classifier -----------------------------------------------------------

CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "documentType": {"type": "string", "enum": ["invoice", "credit_note", "other", "junk"]},
        "typeReasoning": {"type": "string"},
        "sender": {
            "type": "object",
            "properties": {
                "companyName": {"type": "string", "nullable": True},
                "address": {"type": "string", "nullable": True},
                "vatId": {"type": "string", "nullable": True},
            },
        },
        "recipient": {
            "type": "object",
            "properties": {
                "companyName": {"type": "string", "nullable": True},
                "address": {"type": "string", "nullable": True},
                "vatId": {"type": "string", "nullable": True},
            },
        },
    },
    "required": ["documentType", "typeReasoning", "sender", "recipient"],
}


PROMPT = """Classify a document from its OCR text and identify the sender and recipient.

Document types: "invoice", "credit_note", "other", "junk".

Classification rules:
- Classify by CONTEXT, not by the title. A heading "Invoice" does NOT make it an invoice.
- Try the non-invoice types first (junk, other, credit_note). Treat "invoice" as the LAST resort, only if nothing else fits.
- A document is an "invoice" only if it has BOTH (a) a net amount AND (b) a clear sender AND recipient. Otherwise -> "other".
- Override: an invoice with a negative payable amount -> "credit_note".
- "junk" = spam, blank pages, unrelated documents.

Sender / recipient identification:
- The entity with the PAYMENT details (IBAN/SWIFT/bank account) is ALWAYS the sender, never the recipient.
- Take the sender from the FOOTER of the document — full legal name + bank details usually live there.
- Take the recipient only from a place where the name AND full postal address appear TOGETHER. NEVER from running text, a note, or the footer.
- Sender and recipient must be DIFFERENT entities.

Return JSON matching the schema. Keep typeReasoning to one short sentence.

Document text:
---
{raw_text}
---
"""


class _ClassifierClient(Protocol):
    """Subset of the LLM client surface used for classification."""

    def generate_invoice_json(self, model: str, prompt: str, schema: dict) -> str:
        ...


def parse_classification_response(payload: str) -> Classification:
    """Parse an LLM JSON response into a Classification. Public for testing."""
    data = json.loads(payload)

    def party(key: str) -> Party:
        item = data.get(key) or {}
        return Party(
            company_name=item.get("companyName"),
            address=item.get("address"),
            vat_id=item.get("vatId"),
        )

    raw_type = str(data.get("documentType", "other")).strip().lower()
    try:
        doc_type = DocumentType(raw_type)
    except ValueError:
        doc_type = DocumentType.other

    return Classification(
        document_type=doc_type,
        type_reasoning=str(data.get("typeReasoning", "")),
        sender=party("sender"),
        recipient=party("recipient"),
    )


class GeminiClassifier:
    """Classifies a document with an LLM, trying each model in order."""

    def __init__(
        self,
        client: _ClassifierClient,
        model: str = "gemini-3.1-flash-lite-preview",
        fallback_models: list[str] | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._fallback_models = fallback_models or ["gemini-2.5-flash-lite"]

    def classify(self, raw_text: str) -> Classification:
        prompt = PROMPT.format(raw_text=raw_text)
        last_error: Exception | None = None
        for model in [self._model, *self._fallback_models]:
            try:
                payload = self._client.generate_invoice_json(model, prompt, CLASSIFICATION_SCHEMA)
                return parse_classification_response(payload)
            except Exception as exc:  # noqa: BLE001 - fall through any provider error
                last_error = exc
        assert last_error is not None
        raise last_error
