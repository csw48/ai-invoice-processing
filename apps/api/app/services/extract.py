import re

from app.models import ConfidenceValue, ExtractedInvoice


_PATTERNS = {
    "vendor_vat": re.compile(r"\b(SK\d{10})\b"),
    "invoice_number": re.compile(r"(?:invoice|fakt[úu]ra)\s*(?:number|číslo|c\.)?\s*[:#]?\s*([A-Z0-9\-/]+)", re.I),
    "invoice_date": re.compile(r"(?:invoice date|dátum vystavenia|date)\s*:?\s*(\d{1,2}\.\d{1,2}\.\d{4})", re.I),
    "due_date": re.compile(r"(?:due date|splatnosť)\s*:?\s*(\d{1,2}\.\d{1,2}\.\d{4})", re.I),
    "total_amount": re.compile(r"^\s*(?:total|celkom)\s*:?\s*([0-9]+(?:[,.][0-9]{2})?)\s*(EUR|€)?", re.I | re.M),
    "subtotal": re.compile(r"^\s*(?:subtotal|základ)\s*:?\s*([0-9]+(?:[,.][0-9]{2})?)", re.I | re.M),
    "vat_amount": re.compile(r"^\s*(?:vat|dph)\s*:?\s*([0-9]+(?:[,.][0-9]{2})?)", re.I | re.M),
    "vendor_iban": re.compile(r"\b([A-Z]{2}\d{2}[A-Z0-9]{10,30})\b"),
}


def _amount(value: str) -> float:
    return float(value.replace(",", "."))


def _field(text: str, key: str) -> ConfidenceValue:
    match = _PATTERNS[key].search(text)
    if not match:
        return ConfidenceValue(value=None, confidence=0.0)
    value = match.group(1)
    if key in {"subtotal", "vat_amount", "total_amount"}:
        value = _amount(value)
    return ConfidenceValue(value=value, confidence=0.86)


def extract_invoice_fields(raw_text: str) -> ExtractedInvoice:
    """Deterministic MVP extractor; replace with Azure OpenAI structured output later."""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    vendor_name = lines[0] if lines else None
    return ExtractedInvoice(
        vendor_name=ConfidenceValue(value=vendor_name, confidence=0.8 if vendor_name else 0.0),
        vendor_vat=_field(raw_text, "vendor_vat"),
        vendor_iban=_field(raw_text, "vendor_iban"),
        invoice_number=_field(raw_text, "invoice_number"),
        invoice_date=_field(raw_text, "invoice_date"),
        due_date=_field(raw_text, "due_date"),
        subtotal=_field(raw_text, "subtotal"),
        vat_amount=_field(raw_text, "vat_amount"),
        total_amount=_field(raw_text, "total_amount"),
        currency=ConfidenceValue(value="EUR", confidence=0.8 if "EUR" in raw_text or "€" in raw_text else 0.5),
    )
