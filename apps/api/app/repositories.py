from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID, uuid4

from app.models import (
    Classification,
    ClientConfig,
    EnrichedInvoice,
    ExtractedInvoice,
    InvoiceStatus,
    ProcessedInvoice,
    ValidationReport,
    Vendor,
    VendorCreate,
)


class InvoiceRepository(Protocol):
    """Persists processed invoice records, scoped per tenant (client_id)."""

    def save(
        self,
        invoice: ProcessedInvoice,
        file_path: str,
        raw_text: str,
        client_id: str,
        word_positions: list[dict] | None = None,
    ) -> ProcessedInvoice:
        ...

    def get(self, invoice_id: UUID, client_id: str) -> ProcessedInvoice | None:
        ...

    def list(self, client_id: str, limit: int = 50) -> list[ProcessedInvoice]:
        ...

    def update_status(self, invoice_id: UUID, status: InvoiceStatus, client_id: str) -> bool:
        ...

    def is_duplicate(
        self, invoice_number: str, vendor_vat: str, client_id: str, days: int = 90
    ) -> bool:
        ...


class InMemoryInvoiceRepository:
    """In-memory implementation used by tests and local development."""

    def __init__(self) -> None:
        self._invoices: dict[UUID, ProcessedInvoice] = {}
        self._owner: dict[UUID, str] = {}
        self._files: dict[UUID, str] = {}
        self._raw: dict[UUID, str] = {}

    def save(
        self,
        invoice: ProcessedInvoice,
        file_path: str,
        raw_text: str,
        client_id: str,
        word_positions: list[dict] | None = None,
    ) -> ProcessedInvoice:
        saved = invoice.model_copy(
            update={
                "file_path": file_path,
                "raw_text": raw_text,
                "word_positions": word_positions,
            }
        )
        self._invoices[invoice.invoice_id] = saved
        self._owner[invoice.invoice_id] = client_id
        self._files[invoice.invoice_id] = file_path
        self._raw[invoice.invoice_id] = raw_text
        return saved

    def get(self, invoice_id: UUID, client_id: str) -> ProcessedInvoice | None:
        if self._owner.get(invoice_id) != client_id:
            return None
        return self._invoices.get(invoice_id)

    def list(self, client_id: str, limit: int = 50) -> list[ProcessedInvoice]:
        invoices = [
            inv
            for inv in self._invoices.values()
            if inv.status != InvoiceStatus.deleted and self._owner.get(inv.invoice_id) == client_id
        ]
        return invoices[-limit:]

    def update_status(self, invoice_id: UUID, status: InvoiceStatus, client_id: str) -> bool:
        invoice = self._invoices.get(invoice_id)
        if not invoice or self._owner.get(invoice_id) != client_id:
            return False
        self._invoices[invoice_id] = invoice.model_copy(update={"status": status})
        return True

    def is_duplicate(
        self, invoice_number: str, vendor_vat: str, client_id: str, days: int = 90
    ) -> bool:
        for invoice in self._invoices.values():
            if invoice.status == InvoiceStatus.deleted:
                continue
            if self._owner.get(invoice.invoice_id) != client_id:
                continue
            inv_num = invoice.extracted.invoice_number
            inv_vat = invoice.extracted.vendor_vat
            if (
                inv_num is not None
                and inv_vat is not None
                and inv_num.value == invoice_number
                and inv_vat.value == vendor_vat
            ):
                return True
        return False

    def file_path(self, invoice_id: UUID) -> str | None:
        return self._files.get(invoice_id)


def _row_to_invoice(row: dict) -> ProcessedInvoice:
    classification_row = row.get("classification")
    return ProcessedInvoice(
        invoice_id=row["id"],
        status=row["status"],
        classification=Classification.model_validate(classification_row) if classification_row else None,
        extracted=ExtractedInvoice.model_validate(row["extracted"]),
        validation=ValidationReport.model_validate(row["validated"]),
        enriched=EnrichedInvoice.model_validate(row["enriched"]),
        formatted=row["formatted"] or {},
        country_code=row.get("country_code"),
        file_path=row.get("file_path"),
        raw_text=row.get("raw_text"),
        word_positions=row.get("word_positions"),
    )


class SupabaseInvoiceRepository:
    """Supabase Postgres implementation; constructed when env vars are configured."""

    def __init__(self, client) -> None:
        self._client = client

    def save(self, invoice: ProcessedInvoice, file_path: str, raw_text: str, client_id: str, word_positions: list[dict] | None = None) -> ProcessedInvoice:
        row: dict = {
            "id": str(invoice.invoice_id),
            "client_id": client_id,
            "file_path": file_path,
            "status": invoice.status.value,
            "raw_text": raw_text,
            "classification": invoice.classification.model_dump(mode="json") if invoice.classification else None,
            "extracted": invoice.extracted.model_dump(mode="json"),
            "validated": invoice.validation.model_dump(mode="json"),
            "enriched": invoice.enriched.model_dump(mode="json"),
            "formatted": invoice.formatted,
            "country_code": invoice.country_code,
        }
        if word_positions is not None:
            row["word_positions"] = word_positions
        self._client.table("invoices").upsert(row).execute()
        return invoice

    def get(self, invoice_id: UUID, client_id: str) -> ProcessedInvoice | None:
        result = (
            self._client.table("invoices")
            .select("*")
            .eq("id", str(invoice_id))
            .eq("client_id", client_id)
            .maybe_single()
            .execute()
        )
        if result is None or not result.data:
            return None
        return _row_to_invoice(result.data)

    def list(self, client_id: str, limit: int = 50) -> list[ProcessedInvoice]:
        result = (
            self._client.table("invoices")
            .select("*")
            .eq("client_id", client_id)
            .neq("status", "deleted")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [_row_to_invoice(row) for row in (result.data or [])]

    def update_status(self, invoice_id: UUID, status: InvoiceStatus, client_id: str) -> bool:
        result = (
            self._client.table("invoices")
            .update({"status": status.value})
            .eq("id", str(invoice_id))
            .eq("client_id", client_id)
            .execute()
        )
        return len(result.data) > 0

    def is_duplicate(
        self, invoice_number: str, vendor_vat: str, client_id: str, days: int = 90
    ) -> bool:
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()
        result = (
            self._client.table("invoices")
            .select("extracted")
            .eq("client_id", client_id)
            .neq("status", "deleted")
            .gte("created_at", cutoff)
            .execute()
        )
        for row in result.data or []:
            extracted = row.get("extracted") or {}
            inv_num = (extracted.get("invoice_number") or {}).get("value")
            inv_vat = (extracted.get("vendor_vat") or {}).get("value")
            if inv_num == invoice_number and inv_vat == vendor_vat:
                return True
        return False


class VendorRepository(Protocol):
    """Persists vendor knowledge-base records, scoped per tenant (client_id)."""

    def create(self, vendor: VendorCreate, client_id: str) -> Vendor:
        ...

    def list(self, client_id: str, limit: int = 50) -> list[Vendor]:
        ...

    def delete(self, vendor_id: UUID, client_id: str) -> bool:
        ...

    def find_by_vat(self, vat_number: str, client_id: str) -> "Vendor | None":
        ...

    def find_by_name(self, name: str, client_id: str) -> "Vendor | None":
        ...


class InMemoryVendorRepository:
    """In-memory vendor implementation used by tests and local development."""

    def __init__(self) -> None:
        self._vendors: dict[UUID, Vendor] = {}

    def create(self, vendor: VendorCreate, client_id: str) -> Vendor:
        created = Vendor(id=uuid4(), **{**vendor.model_dump(), "client_id": client_id})
        self._vendors[created.id] = created
        return created

    def list(self, client_id: str, limit: int = 50) -> list[Vendor]:
        vendors = [v for v in self._vendors.values() if v.client_id == client_id]
        return vendors[-limit:]

    def delete(self, vendor_id: UUID, client_id: str) -> bool:
        vendor = self._vendors.get(vendor_id)
        if vendor is None or vendor.client_id != client_id:
            return False
        del self._vendors[vendor_id]
        return True

    def find_by_vat(self, vat_number: str, client_id: str) -> "Vendor | None":
        for vendor in self._vendors.values():
            if (
                vendor.client_id == client_id
                and vendor.vat_number
                and vendor.vat_number.lower() == vat_number.lower()
            ):
                return vendor
        return None

    def find_by_name(self, name: str, client_id: str) -> "Vendor | None":
        name_lower = name.lower()
        for vendor in self._vendors.values():
            if vendor.client_id == client_id and name_lower in vendor.name.lower():
                return vendor
        return None


def _row_to_vendor(row: dict) -> Vendor:
    return Vendor(
        id=row["id"],
        client_id=row.get("client_id"),
        name=row["name"],
        vat_number=row.get("vat_number"),
        iban=row.get("iban"),
        category=row.get("category"),
        metadata=row.get("metadata") or {},
    )


class SupabaseVendorRepository:
    """Supabase Postgres implementation for the vendor knowledge base."""

    def __init__(self, client) -> None:
        self._client = client

    def create(self, vendor: VendorCreate, client_id: str) -> Vendor:
        row = vendor.model_dump(mode="json")
        row["id"] = str(uuid4())
        row["client_id"] = client_id
        result = self._client.table("vendors").insert(row).execute()
        return _row_to_vendor(result.data[0])

    def list(self, client_id: str, limit: int = 50) -> list[Vendor]:
        result = (
            self._client.table("vendors")
            .select("*")
            .eq("client_id", client_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [_row_to_vendor(row) for row in (result.data or [])]

    def delete(self, vendor_id: UUID, client_id: str) -> bool:
        result = (
            self._client.table("vendors")
            .delete()
            .eq("id", str(vendor_id))
            .eq("client_id", client_id)
            .execute()
        )
        return len(result.data) > 0

    def find_by_vat(self, vat_number: str, client_id: str) -> "Vendor | None":
        result = (
            self._client.table("vendors")
            .select("*")
            .eq("client_id", client_id)
            .eq("vat_number", vat_number)
            .maybe_single()
            .execute()
        )
        if result is None or not result.data:
            return None
        return _row_to_vendor(result.data)

    def find_by_name(self, name: str, client_id: str) -> "Vendor | None":
        result = (
            self._client.table("vendors")
            .select("*")
            .eq("client_id", client_id)
            .ilike("name", f"%{name}%")
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return None
        return _row_to_vendor(rows[0])


class ConfigRepository:
    """Persists client config to Supabase, keyed by client_id (one row per client).

    Falls back to an in-memory default when Supabase is not configured (client is None)."""

    DEFAULT_ID = "default"

    def __init__(self, client) -> None:
        self._client = client

    def load(self, client_id: str = DEFAULT_ID) -> ClientConfig:
        if self._client is None:
            return ClientConfig()
        result = (
            self._client.table("client_configs")
            .select("config")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
        if result is None or not result.data:
            return ClientConfig()
        return ClientConfig.model_validate(result.data["config"])

    def save(self, config: ClientConfig, client_id: str = DEFAULT_ID) -> None:
        if self._client is None:
            return
        self._client.table("client_configs").upsert({
            "id": client_id,
            "config": config.model_dump(mode="json"),
            "updated_at": "now()",
        }).execute()
