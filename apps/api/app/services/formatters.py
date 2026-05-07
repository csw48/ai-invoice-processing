import csv
import io
from xml.etree.ElementTree import Element, SubElement, tostring

from app.models import EnrichedInvoice


def format_invoice(enriched: EnrichedInvoice, connector: str) -> dict[str, str | dict]:
    data = enriched.extracted.model_dump(mode="json")
    if connector == "json":
        return {"type": "json", "payload": data}
    if connector == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["vendor_name", "invoice_number", "invoice_date", "total_amount", "currency"])
        writer.writeheader()
        writer.writerow({key: data[key]["value"] for key in writer.fieldnames})
        return {"type": "csv", "payload": output.getvalue()}
    if connector == "pohoda":
        root = Element("dat:dataPack", {"version": "2.0"})
        item = SubElement(root, "dat:dataPackItem")
        invoice = SubElement(item, "inv:invoice")
        header = SubElement(invoice, "inv:invoiceHeader")
        SubElement(header, "inv:number").text = str(data["invoice_number"]["value"] or "")
        SubElement(header, "inv:partnerIdentity").text = str(data["vendor_name"]["value"] or "")
        SubElement(header, "inv:price").text = str(data["total_amount"]["value"] or "")
        return {"type": "pohoda", "payload": tostring(root, encoding="unicode")}
    raise ValueError(f"Unsupported connector: {connector}")
