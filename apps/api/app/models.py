from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class InvoiceStatus(StrEnum):
    processing = "processing"
    review = "review"
    approved = "approved"
    exported = "exported"
    error = "error"
    deleted = "deleted"
    redirect = "redirect"  # classified as "other" — needs manual handling
    discarded = "discarded"  # classified as "junk"


class DocumentType(StrEnum):
    invoice = "invoice"
    credit_note = "credit_note"
    other = "other"
    junk = "junk"


class Party(BaseModel):
    """A sender or recipient identified during classification."""
    company_name: str | None = None
    address: str | None = None
    vat_id: str | None = None


class Classification(BaseModel):
    document_type: DocumentType = DocumentType.invoice
    type_reasoning: str = ""
    sender: Party = Field(default_factory=Party)
    recipient: Party = Field(default_factory=Party)

    @property
    def needs_extraction(self) -> bool:
        return self.document_type in (DocumentType.invoice, DocumentType.credit_note)


class ConfidenceValue(BaseModel):
    value: Any = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class LineItem(BaseModel):
    description: str = ""
    qty: float = 0
    unit_price: float = 0
    vat_rate: float = 0
    total: float = 0


class TaxLine(BaseModel):
    rate: float = 0.0    # VAT rate as decimal (e.g. 0.23 for 23%)
    base: float = 0.0    # net base amount for this rate band
    amount: float = 0.0  # tax amount for this rate band


class ExtractedInvoice(BaseModel):
    vendor_name: ConfidenceValue = Field(default_factory=ConfidenceValue)
    vendor_ico: ConfidenceValue = Field(default_factory=ConfidenceValue)
    vendor_vat: ConfidenceValue = Field(default_factory=ConfidenceValue)
    vendor_iban: ConfidenceValue = Field(default_factory=ConfidenceValue)
    invoice_number: ConfidenceValue = Field(default_factory=ConfidenceValue)
    invoice_date: ConfidenceValue = Field(default_factory=ConfidenceValue)
    # Service / delivery date (Leistungsdatum / Lieferdatum / dátum dodania).
    # Falls back to invoice_date when the document does not state one.
    delivered_at: ConfidenceValue = Field(default_factory=ConfidenceValue)
    due_date: ConfidenceValue = Field(default_factory=ConfidenceValue)
    subtotal: ConfidenceValue = Field(default_factory=ConfidenceValue)
    vat_amount: ConfidenceValue = Field(default_factory=ConfidenceValue)
    total_amount: ConfidenceValue = Field(default_factory=ConfidenceValue)
    currency: ConfidenceValue = Field(default_factory=lambda: ConfidenceValue(value="EUR", confidence=0.5))
    po_number: ConfidenceValue = Field(default_factory=ConfidenceValue)
    cost_center: ConfidenceValue = Field(default_factory=ConfidenceValue)
    # Recipient (buyer / odberateľ) — the party the invoice is addressed to.
    recipient_name: ConfidenceValue = Field(default_factory=ConfidenceValue)
    recipient_vat: ConfidenceValue = Field(default_factory=ConfidenceValue)
    recipient_address: ConfidenceValue = Field(default_factory=ConfidenceValue)
    recipient_postcode: ConfidenceValue = Field(default_factory=ConfidenceValue)
    recipient_city: ConfidenceValue = Field(default_factory=ConfidenceValue)
    recipient_country: ConfidenceValue = Field(default_factory=ConfidenceValue)
    line_items: list[LineItem] = Field(default_factory=list)
    tax_lines: list[TaxLine] = Field(default_factory=list)
    amount_due: ConfidenceValue = Field(default_factory=ConfidenceValue)


class ValidationIssue(BaseModel):
    field: str
    severity: str
    message: str
    # Stable machine-readable code (brief Step 3): E02 (missing net/gross/tax),
    # E03 (net + tax != gross), E04 (incomplete supplier), E05 (incomplete recipient).
    # None for checks outside the brief's code set (VAT format, currency, dates).
    code: str | None = None


class ValidationReport(BaseModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class ClientConfig(BaseModel):
    client_id: UUID = Field(default_factory=uuid4)
    name: str = "Demo Firma s.r.o."
    country_code: str | None = None  # auto-detected when None
    fields_required: list[str] = Field(default_factory=lambda: [
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "total_amount",
    ])
    fields_optional: list[str] = Field(default_factory=lambda: ["po_number", "cost_center"])
    # validation_rules can OVERRIDE country profile values; leave empty to use the profile.
    validation_rules: dict[str, Any] = Field(default_factory=dict)
    output_connector: str = "json"
    connector_config: dict[str, Any] = Field(default_factory=dict)
    language: str = "auto"
    confidence_threshold: float = 0.75


class EnrichedInvoice(BaseModel):
    extracted: ExtractedInvoice
    vendor_metadata: dict[str, Any] = Field(default_factory=dict)
    duplicate: bool = False
    category: str | None = None
    vat_mismatch: bool = False
    stored_vat: str | None = None


class ProcessedInvoice(BaseModel):
    invoice_id: UUID = Field(default_factory=uuid4)
    status: InvoiceStatus = InvoiceStatus.review
    classification: Classification | None = None
    extracted: ExtractedInvoice
    validation: ValidationReport
    enriched: EnrichedInvoice
    formatted: dict[str, Any]
    country_code: str | None = None
    file_path: str | None = None
    raw_text: str | None = None
    word_positions: list[dict] | None = None
    # Field keys a reviewer manually corrected — feeds per-field accuracy stats.
    edited_fields: list[str] = Field(default_factory=list)


class VendorCreate(BaseModel):
    name: str
    client_id: str | None = None
    vat_number: str | None = None
    iban: str | None = None
    category: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Vendor(VendorCreate):
    id: UUID = Field(default_factory=uuid4)
