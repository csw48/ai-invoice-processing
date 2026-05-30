import csv
import io
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


def _pohoda_xml(enriched: EnrichedInvoice) -> str:
    data = enriched.extracted.model_dump(mode="json")

    root = Element(
        "dat:dataPack",
        {
            "id": "factura-export",
            "ico": enriched.vendor_metadata.get("ico", ""),
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
    SubElement(header, "inv:invoiceType").text = "receivedInvoice"

    inv_num = _val(data, "invoice_number")
    num_el = SubElement(header, "inv:number")
    SubElement(num_el, "typ:numberRequested").text = inv_num

    SubElement(header, "inv:symVar").text = inv_num
    SubElement(header, "inv:date").text = _val(data, "invoice_date")
    SubElement(header, "inv:dateTax").text = _val(data, "invoice_date")

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

    # Bank account (IBAN)
    iban = _val(data, "vendor_iban") or enriched.vendor_metadata.get("iban", "")
    if iban:
        account_el = SubElement(header, "inv:account")
        SubElement(account_el, "typ:accountNo").text = str(iban)

    SubElement(header, "inv:text").text = f"Prijatá faktúra {inv_num}"

    # ── Summary ─────────────────────────────────────────────────────
    summary = SubElement(invoice, "inv:invoiceSummary")
    home = SubElement(summary, "inv:homeCurrency")

    def _price_el(parent: Element, tag: str, key: str) -> None:
        v = _val(data, key)
        SubElement(parent, tag).text = v if v else "0"

    _price_el(home, "typ:priceHigh", "subtotal")
    _price_el(home, "typ:priceHighVAT", "vat_amount")
    _price_el(home, "typ:priceHighSum", "total_amount")

    round_el = SubElement(home, "typ:round")
    SubElement(round_el, "typ:priceRound").text = "0"

    xml_bytes = tostring(root, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes


def format_invoice(enriched: EnrichedInvoice, connector: str) -> dict[str, str | dict]:
    data = enriched.extracted.model_dump(mode="json")
    if connector == "json":
        return {"type": "json", "payload": data}
    if connector == "csv":
        output = io.StringIO()
        fields = ["vendor_name", "invoice_number", "invoice_date", "total_amount", "currency"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerow({key: _val(data, key) for key in fields})
        return {"type": "csv", "payload": output.getvalue()}
    if connector == "pohoda":
        return {"type": "pohoda", "payload": _pohoda_xml(enriched)}
    if connector == "webhook":
        # Payload is the full extracted data; the endpoint URL is resolved at export time
        # from connector_config, not stored here.
        return {"type": "webhook", "payload": data}
    raise ValueError(f"Unsupported connector: {connector}")
