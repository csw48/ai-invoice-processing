from app.models import EnrichedInvoice, ExtractedInvoice
from app.repositories import InvoiceRepository, VendorRepository


def enrich_invoice(
    extracted: ExtractedInvoice,
    vendor_repo: VendorRepository | None,
    invoice_repo: InvoiceRepository | None,
    client_id: str,
) -> EnrichedInvoice:
    """Look up vendor metadata and check for duplicate invoices within the tenant.

    When vendor_repo is None the function is a no-op for backward compatibility.
    """
    if vendor_repo is None:
        return EnrichedInvoice(extracted=extracted)

    vendor_vat = extracted.vendor_vat.value if extracted.vendor_vat else None
    vendor_name = extracted.vendor_name.value if extracted.vendor_name else None

    # Try VAT lookup first, fall back to name lookup.
    vendor = None
    if vendor_vat:
        vendor = vendor_repo.find_by_vat(vendor_vat, client_id)
    if vendor is None and vendor_name:
        vendor = vendor_repo.find_by_name(vendor_name, client_id)

    vendor_metadata: dict = {}
    category: str | None = None
    if vendor is not None:
        vendor_metadata = {
            "id": str(vendor.id),
            "name": vendor.name,
            "iban": vendor.iban,
            "category": vendor.category,
            **vendor.metadata,
        }
        category = vendor.category

    # Duplicate check requires both invoice number and vendor VAT.
    duplicate = False
    invoice_number = extracted.invoice_number.value if extracted.invoice_number else None
    if invoice_repo is not None and invoice_number and vendor_vat:
        duplicate = invoice_repo.is_duplicate(invoice_number, vendor_vat, client_id)

    return EnrichedInvoice(
        extracted=extracted,
        vendor_metadata=vendor_metadata,
        duplicate=duplicate,
        category=category,
    )
