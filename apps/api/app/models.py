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


class ConfidenceValue(BaseModel):
    value: Any = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class LineItem(BaseModel):
    description: str = ""
    qty: float = 0
    unit_price: float = 0
    vat_rate: float = 0
    total: float = 0


class ExtractedInvoice(BaseModel):
    vendor_name: ConfidenceValue = Field(default_factory=ConfidenceValue)
    vendor_vat: ConfidenceValue = Field(default_factory=ConfidenceValue)
    vendor_iban: ConfidenceValue = Field(default_factory=ConfidenceValue)
    invoice_number: ConfidenceValue = Field(default_factory=ConfidenceValue)
    invoice_date: ConfidenceValue = Field(default_factory=ConfidenceValue)
    due_date: ConfidenceValue = Field(default_factory=ConfidenceValue)
    subtotal: ConfidenceValue = Field(default_factory=ConfidenceValue)
    vat_amount: ConfidenceValue = Field(default_factory=ConfidenceValue)
    total_amount: ConfidenceValue = Field(default_factory=ConfidenceValue)
    currency: ConfidenceValue = Field(default_factory=lambda: ConfidenceValue(value="EUR", confidence=0.5))
    po_number: ConfidenceValue = Field(default_factory=ConfidenceValue)
    cost_center: ConfidenceValue = Field(default_factory=ConfidenceValue)
    line_items: list[LineItem] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    field: str
    severity: str
    message: str


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


class ProcessedInvoice(BaseModel):
    invoice_id: UUID = Field(default_factory=uuid4)
    status: InvoiceStatus = InvoiceStatus.review
    extracted: ExtractedInvoice
    validation: ValidationReport
    enriched: EnrichedInvoice
    formatted: dict[str, Any]
    country_code: str | None = None  # detected country, attached to processed result
