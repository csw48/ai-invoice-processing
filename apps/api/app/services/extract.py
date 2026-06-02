import re

from app.models import ConfidenceValue, ExtractedInvoice, LineItem
from app.services.normalize import normalize_number


_PATTERNS = {
    "vendor_vat": re.compile(r"\b(SK\d{10})\b"),
    "invoice_number": re.compile(r"(?:invoice|fakt[úu]ra)\s*(?:number|číslo|c\.)?\s*[:#]?\s*([A-Z0-9\-/]+)", re.I),
    "invoice_date": re.compile(r"(?:invoice date|dátum vystavenia|date)\s*:?\s*(\d{1,2}\.\d{1,2}\.\d{4})", re.I),
    "delivered_at": re.compile(r"(?:delivery date|date of supply|dátum dodania|leistungsdatum|lieferdatum)\s*:?\s*(\d{1,2}\.\d{1,2}\.\d{4})", re.I),
    "due_date": re.compile(r"(?:due date|splatnosť)\s*:?\s*(\d{1,2}\.\d{1,2}\.\d{4})", re.I),
    "total_amount": re.compile(r"^\s*(?:total|celkom)\s*:?\s*([0-9]+(?:[,.][0-9]{2})?)\s*(EUR|€)?", re.I | re.M),
    "subtotal": re.compile(r"^\s*(?:subtotal|základ)\s*:?\s*([0-9]+(?:[,.][0-9]{2})?)", re.I | re.M),
    "vat_amount": re.compile(r"^\s*(?:vat|dph)\s*:?\s*([0-9]+(?:[,.][0-9]{2})?)", re.I | re.M),
    "vendor_iban": re.compile(r"\b([A-Z]{2}\d{2}[A-Z0-9]{10,30})\b"),
}
_QTY_RE = re.compile(r"^\d+(?:[,.]\d+)?$")
_VAT_RATE_RE = re.compile(r"^(\d{1,2}(?:[,.]\d+)?)\s*%$")
_MONEY_RE = re.compile(r"(?:€\s*)?([0-9][0-9 .]*(?:[,.]\d{2}))\s*(?:€|EUR|Kč|CZK)?", re.I)
_UNIT_LINES = {"ks", "kus", "kusy", "pcs", "pc", "x"}
_NON_DESCRIPTION_LINES = {
    "cena za mj",
    "celkom bez dph",
    "celkem bez dph",
    "dph",
    "zadarmo",
    "zdarma",
}
_SUMMARY_MARKERS = {"sadzba", "základ", "zaklad", "spolu", "celkom", "celkem", "total"}


def _amount(value: str) -> float:
    # Strip ASCII and non-breaking spaces used as thousands separators.
    s = value.replace(" ", "").replace(" ", "")
    last_dot = s.rfind(".")
    last_comma = s.rfind(",")
    if last_comma > last_dot:
        # Comma is the decimal separator (EU): dots are thousands separators.
        s = s.replace(".", "").replace(",", ".")
    else:
        # Dot is the decimal separator (US) or there is no comma: commas are thousands.
        s = s.replace(",", "")
    return float(s)


def _field(text: str, key: str) -> ConfidenceValue:
    match = _PATTERNS[key].search(text)
    if not match:
        return ConfidenceValue(value=None, confidence=0.0)
    value = match.group(1)
    if key in {"subtotal", "vat_amount", "total_amount"}:
        value = _amount(value)
    elif key == "invoice_number":
        value = normalize_number(value)
    return ConfidenceValue(value=value, confidence=0.86)


def _is_qty(line: str) -> bool:
    return bool(_QTY_RE.fullmatch(line.strip()))


def _is_unit(line: str) -> bool:
    return line.strip().lower() in _UNIT_LINES


def _money(line: str) -> float | None:
    match = _MONEY_RE.search(line)
    if not match:
        return None
    return _amount(match.group(1))


def _vat_rate(line: str) -> float | None:
    match = _VAT_RATE_RE.fullmatch(line.strip())
    if not match:
        return None
    return _amount(match.group(1)) / 100


def _is_summary_start(line: str) -> bool:
    return line.strip().lower() in _SUMMARY_MARKERS


def parse_line_items(raw_text: str) -> list[LineItem]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    items: list[LineItem] = []
    i = 0
    while i < len(lines) - 4:
        if not (_is_qty(lines[i]) and _is_unit(lines[i + 1])):
            i += 1
            continue

        qty = _amount(lines[i])
        description_lines: list[str] = []
        j = i + 2
        while j < len(lines):
            if _vat_rate(lines[j]) is not None:
                break
            if _is_summary_start(lines[j]) or _money(lines[j]) is not None:
                break

            description_line = lines[j]
            if description_line.lower() not in _NON_DESCRIPTION_LINES:
                description_lines.append(description_line)
            j += 1

        if not description_lines or j >= len(lines):
            i += 1
            continue

        vat_rate = _vat_rate(lines[j])
        if vat_rate is None:
            i += 1
            continue

        amounts: list[float] = []
        k = j + 1
        while k < len(lines) and len(amounts) < 2:
            if k + 1 < len(lines) and _is_qty(lines[k]) and _is_unit(lines[k + 1]):
                break
            if _is_summary_start(lines[k]):
                break
            amount = _money(lines[k])
            if amount is not None:
                amounts.append(amount)
            k += 1

        if amounts:
            unit_price = amounts[0]
            total = amounts[1] if len(amounts) > 1 else round(qty * unit_price, 2)
            items.append(
                LineItem(
                    description=" ".join(description_lines),
                    qty=qty,
                    unit_price=unit_price,
                    vat_rate=vat_rate,
                    total=total,
                )
            )
            i = k
            continue

        i += 1

    return items


def fill_delivered_at(extracted: ExtractedInvoice) -> ExtractedInvoice:
    """Brief Step 2: when no delivery/service date was found, fall back to issued date.

    The fallback is a defined rule, so it inherits the invoice_date confidence — it
    must not trip the low-confidence review flag any more than the issue date does.
    """
    if extracted.delivered_at.value not in (None, ""):
        return extracted
    invoice_date = extracted.invoice_date
    if invoice_date.value in (None, ""):
        return extracted
    return extracted.model_copy(update={"delivered_at": invoice_date.model_copy()})


def fill_missing_line_items(extracted: ExtractedInvoice, raw_text: str) -> ExtractedInvoice:
    parsed_items = parse_line_items(raw_text)
    if not parsed_items:
        return extracted

    existing_items_have_prices = any(item.qty and item.unit_price and item.total for item in extracted.line_items)
    if existing_items_have_prices:
        return extracted

    return extracted.model_copy(update={"line_items": parsed_items})


def extract_invoice_fields(raw_text: str) -> ExtractedInvoice:
    """Deterministic MVP extractor; replace with Azure OpenAI structured output later."""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    vendor_name = lines[0] if lines else None
    extracted = ExtractedInvoice(
        vendor_name=ConfidenceValue(value=vendor_name, confidence=0.8 if vendor_name else 0.0),
        vendor_vat=_field(raw_text, "vendor_vat"),
        vendor_iban=_field(raw_text, "vendor_iban"),
        invoice_number=_field(raw_text, "invoice_number"),
        invoice_date=_field(raw_text, "invoice_date"),
        delivered_at=_field(raw_text, "delivered_at"),
        due_date=_field(raw_text, "due_date"),
        subtotal=_field(raw_text, "subtotal"),
        vat_amount=_field(raw_text, "vat_amount"),
        total_amount=_field(raw_text, "total_amount"),
        currency=ConfidenceValue(value="EUR", confidence=0.8 if "EUR" in raw_text or "€" in raw_text else 0.5),
    )
    return fill_missing_line_items(extracted, raw_text)
