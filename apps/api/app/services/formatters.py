import csv
import io
import re
from xml.etree.ElementTree import Element, SubElement, tostring

from app.models import EnrichedInvoice

# Pohoda XML namespaces (RADVYD = received invoice schema v2.0)
_NS = {
    "dat": "http://www.stormware.cz/schema/version_2/data.xsd",
    "inv": "http://www.stormware.cz/schema/version_2/invoice.xsd",
    "typ": "http://www.stormware.cz/schema/version_2/type.xsd",
}


def _val(data: dict, key: str) -> str:
    item = data.get(key) or {}
    v = item.get("value") if isinstance(item, dict) else None
    return str(v) if v is not None and v != "" else ""


def _vat_band(rate: float, max_rate: float | None) -> str:
    """Map a numeric VAT rate to a Pohoda band: none / low / high.

    The highest rate present on the invoice is treated as the standard ("high")
    band; any lower non-zero rate is "low"; zero / exempt is "none". This adapts
    per invoice without needing per-country rate tables.
    """
    if not rate:
        return "none"
    if max_rate is not None and rate >= max_rate:
        return "high"
    return "low"


def _money(value: float) -> str:
    # Pohoda expects a dot decimal separator and at most 2 decimals.
    return f"{round(float(value), 2):.2f}"


def _pohoda_xml(enriched: EnrichedInvoice, document_type: str = "invoice", connector_config: dict | None = None) -> str:
    data = enriched.extracted.model_dump(mode="json")
    is_credit = document_type == "credit_note"
    # dataPack ico = the client/buyer company ICO (from connector config), not the vendor's.
    client_ico = (connector_config or {}).get("ico", "")

    root = Element(
        "dat:dataPack",
        {
            "id": "factura-export",
            "ico": client_ico,
            "application": "Factura",
            "version": "2.0",
            "note": "Pohoda XML export",
            "xmlns:dat": _NS["dat"],
            "xmlns:inv": _NS["inv"],
            "xmlns:typ": _NS["typ"],
        },
    )

    pack_item = SubElement(root, "dat:dataPackItem", {"id": "1", "version": "2.0"})
    invoice = SubElement(pack_item, "inv:invoice", {"version": "2.0"})

    # ── Header ──────────────────────────────────────────────────────
    header = SubElement(invoice, "inv:invoiceHeader")
    SubElement(header, "inv:invoiceType").text = "receivedCreditNotice" if is_credit else "receivedInvoice"

    inv_num = _val(data, "invoice_number")
    num_el = SubElement(header, "inv:number")
    SubElement(num_el, "typ:numberRequested").text = inv_num

    # symVar is the bank variable symbol: digits only, max 10 chars.
    sym_var = re.sub(r"[^\d]", "", inv_num)[:10]
    if sym_var:
        SubElement(header, "inv:symVar").text = sym_var
    SubElement(header, "inv:date").text = _val(data, "invoice_date")
    # Tax point = delivery/service date when stated, else the issue date.
    SubElement(header, "inv:dateTax").text = _val(data, "delivered_at") or _val(data, "invoice_date")

    due = _val(data, "due_date")
    if due:
        SubElement(header, "inv:datePayment").text = due

    # Partner identity (vendor)
    partner = SubElement(header, "inv:partnerIdentity")
    addr = SubElement(partner, "typ:address")
    SubElement(addr, "typ:company").text = _val(data, "vendor_name")
    vat = _val(data, "vendor_vat")
    if vat:
        SubElement(addr, "typ:dic").text = vat

    # My identity (recipient / buyer) — only emitted when a recipient was extracted.
    if _val(data, "recipient_name"):
        my = SubElement(header, "inv:myIdentity")
        my_addr = SubElement(my, "typ:address")
        SubElement(my_addr, "typ:company").text = _val(data, "recipient_name")
        for tag, key in (("typ:street", "recipient_address"), ("typ:city", "recipient_city"), ("typ:zip", "recipient_postcode")):
            v = _val(data, key)
            if v:
                SubElement(my_addr, tag).text = v
        rec_vat = _val(data, "recipient_vat")
        if rec_vat:
            SubElement(my_addr, "typ:dic").text = rec_vat

    # Bank account (IBAN)
    iban = _val(data, "vendor_iban") or enriched.vendor_metadata.get("iban", "")
    if iban:
        account_el = SubElement(header, "inv:account")
        SubElement(account_el, "typ:accountNo").text = str(iban)

    SubElement(header, "inv:text").text = f"{'Dobropis' if is_credit else 'Prijatá faktúra'} {inv_num}".strip()

    # ── Detail (line items) ─────────────────────────────────────────
    items = enriched.extracted.line_items
    rates = [li.vat_rate for li in items if li.vat_rate]
    max_rate = max(rates) if rates else None
    # Per-band aggregates for the summary: base (net) and VAT, keyed by band.
    bands: dict[str, dict[str, float]] = {}

    if items:
        detail = SubElement(invoice, "inv:invoiceDetail")
        for li in items:
            band = _vat_band(li.vat_rate, max_rate)
            base = float(li.total or 0)
            vat = round(base * float(li.vat_rate or 0), 2)
            acc = bands.setdefault(band, {"base": 0.0, "vat": 0.0})
            acc["base"] += base
            acc["vat"] += vat

            item_el = SubElement(detail, "inv:invoiceItem")
            SubElement(item_el, "inv:text").text = li.description or ""
            SubElement(item_el, "inv:quantity").text = _money(li.qty or 0)
            SubElement(item_el, "inv:rateVAT").text = band
            home_item = SubElement(item_el, "inv:homeCurrency")
            SubElement(home_item, "typ:unitPrice").text = _money(li.unit_price or 0)
            SubElement(home_item, "typ:price").text = _money(base)
            SubElement(home_item, "typ:priceVAT").text = _money(vat)

    # ── Summary ─────────────────────────────────────────────────────
    summary = SubElement(invoice, "inv:invoiceSummary")
    home = SubElement(summary, "inv:homeCurrency")

    _BAND_TAGS = {
        "none": ("typ:priceNone", None),
        "low": ("typ:priceLow", "typ:priceLowVAT"),
        "high": ("typ:priceHigh", "typ:priceHighVAT"),
    }

    if bands:
        # Emit one base (+ VAT) pair per VAT band actually present on the invoice.
        for band in ("none", "low", "high"):
            if band not in bands:
                continue
            base_tag, vat_tag = _BAND_TAGS[band]
            SubElement(home, base_tag).text = _money(bands[band]["base"])
            if vat_tag is not None:
                SubElement(home, vat_tag).text = _money(bands[band]["vat"])
    else:
        # No line items parsed — fall back to the flat extracted totals as a single
        # standard-rate band (preserves behaviour for summary-only invoice text).
        def _price_el(tag: str, key: str) -> None:
            v = _val(data, key)
            SubElement(home, tag).text = v if v else "0"

        _price_el("typ:priceHigh", "subtotal")
        _price_el("typ:priceHighVAT", "vat_amount")
        _price_el("typ:priceHighSum", "total_amount")

    round_el = SubElement(home, "typ:round")
    SubElement(round_el, "typ:priceRound").text = "0"

    xml_bytes = tostring(root, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes


def format_invoice(enriched: EnrichedInvoice, connector: str, document_type: str = "invoice", connector_config: dict | None = None) -> dict[str, str | dict]:
    data = enriched.extracted.model_dump(mode="json")
    if connector == "json":
        return {"type": "json", "document_type": document_type, "payload": data}
    if connector == "csv":
        output = io.StringIO()
        fields = [
            "vendor_name", "vendor_vat", "vendor_iban",
            "invoice_number", "invoice_date", "due_date",
            "subtotal", "vat_amount", "total_amount", "currency",
            "recipient_name", "recipient_vat",
        ]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerow({key: _val(data, key) for key in fields})
        return {"type": "csv", "document_type": document_type, "payload": output.getvalue()}
    if connector == "pohoda":
        return {"type": "pohoda", "document_type": document_type, "payload": _pohoda_xml(enriched, document_type, connector_config)}
    if connector == "webhook":
        # Payload is the full extracted data; the endpoint URL is resolved at export time
        # from connector_config, not stored here.
        return {"type": "webhook", "document_type": document_type, "payload": data}
    raise ValueError(f"Unsupported connector: {connector}")
