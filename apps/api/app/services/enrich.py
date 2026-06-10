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
    matched_by_name = False
    if vendor_vat:
        vendor = vendor_repo.find_by_vat(vendor_vat, client_id)
    if vendor is None and vendor_name:
        vendor = vendor_repo.find_by_name(vendor_name, client_id)
        matched_by_name = vendor is not None

    vendor_metadata: dict = {}
    category: str | None = None
    vat_mismatch = False
    stored_vat: str | None = None
    if vendor is not None:
        vendor_metadata = {
            "id": str(vendor.id),
            "name": vendor.name,
            "iban": vendor.iban,
            "category": vendor.category,
            **vendor.metadata,
        }
        category = vendor.category
        # When matched by name, flag if the extracted VAT differs from stored VAT.
        if matched_by_name and vendor_vat and vendor.vat_number and vendor_vat.lower() != vendor.vat_number.lower():
            vat_mismatch = True
            stored_vat = vendor.vat_number

    # Duplicate check — passes date/amount/name for fuzzy multi-signal detection.
    duplicate = False
    invoice_number = extracted.invoice_number.value if extracted.invoice_number else None
    if invoice_repo is not None and invoice_number:
        invoice_date = extracted.invoice_date.value if extracted.invoice_date else None
        net_amount = (
            float(extracted.subtotal.value)
            if extracted.subtotal and extracted.subtotal.value is not None
            else None
        )
        duplicate = invoice_repo.is_duplicate(
            invoice_number,
            vendor_vat,
            client_id,
            invoice_date=str(invoice_date) if invoice_date is not None else None,
            net_amount=net_amount,
            vendor_name=vendor_name,
        )

    return EnrichedInvoice(
        extracted=extracted,
        vendor_metadata=vendor_metadata,
        duplicate=duplicate,
        category=category,
        vat_mismatch=vat_mismatch,
        stored_vat=stored_vat,
    )
