from typing import Protocol
from uuid import UUID

from app.models import ProcessedInvoice


class InvoiceRepository(Protocol):
    """Persists processed invoice records."""

    def save(self, invoice: ProcessedInvoice, file_path: str, raw_text: str) -> ProcessedInvoice:
        ...

    def get(self, invoice_id: UUID) -> ProcessedInvoice | None:
        ...


class InMemoryInvoiceRepository:
    """In-memory implementation used by tests and local development."""

    def __init__(self) -> None:
        self._invoices: dict[UUID, ProcessedInvoice] = {}
        self._files: dict[UUID, str] = {}
        self._raw: dict[UUID, str] = {}

    def save(self, invoice: ProcessedInvoice, file_path: str, raw_text: str) -> ProcessedInvoice:
        self._invoices[invoice.invoice_id] = invoice
        self._files[invoice.invoice_id] = file_path
        self._raw[invoice.invoice_id] = raw_text
        return invoice

    def get(self, invoice_id: UUID) -> ProcessedInvoice | None:
        return self._invoices.get(invoice_id)

    def file_path(self, invoice_id: UUID) -> str | None:
        return self._files.get(invoice_id)
