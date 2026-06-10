from typing import Any
from uuid import UUID
from uuid import uuid4

# Load .env into os.environ so os.getenv() works for all vars (e.g. LOCAL_LLM_URL)
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)  # don't override vars already set in shell
except ImportError:
    pass

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.auth import get_client_id
from app.core.config import get_settings
from app.deps import get_classifier, get_config_repository, get_extractor, get_log_fn, get_repository, get_storage, get_vendor_repository
from app.repositories import ConfigRepository
from app.country_profiles import detect_country
from app.models import Classification, ClientConfig, ConfidenceValue, DocumentType, ExtractedInvoice, InvoiceStatus, ProcessedInvoice, VendorCreate
from app.repositories import InvoiceRepository, VendorRepository
from app.services.classify import classify_document
from app.services.enrich import enrich_invoice
from app.services.formatters import format_invoice
from app.services.log import BufferedLogFn
from app.services.pdf import extract_pdf_text_with_positions
from app.services.pipeline import process_invoice
from app.services.validate import validate_invoice
from app.storage import FileStorage

app = FastAPI(title="AI Invoice Processing API", version="0.1.0")

# Per-client config cache — loaded from Supabase on first access, written through on PUT.
# Keyed by the verified tenant id from get_client_id (Clerk claim, or "default").
_config_cache: dict[str, ClientConfig] = {}


def _load_active_config(client_id: str) -> ClientConfig:
    if client_id not in _config_cache:
        _config_cache[client_id] = get_config_repository().load(client_id)
    return _config_cache[client_id]


def get_active_config(client_id: str = Depends(get_client_id)) -> ClientConfig:
    return _load_active_config(client_id)

_cors_origins = get_settings().cors_origins
_allowed_origins = (
    ["*"] if _cors_origins.strip() == "*"
    else [origin.strip() for origin in _cors_origins.split(",") if origin.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/invoices/upload")
async def upload_invoice(
    file: UploadFile = File(...),
    storage: FileStorage = Depends(get_storage),
    repository: InvoiceRepository = Depends(get_repository),
    vendor_repository: VendorRepository = Depends(get_vendor_repository),
    config: ClientConfig = Depends(get_active_config),
    client_id: str = Depends(get_client_id),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    filename = file.filename or "invoice.pdf"
    word_positions: list[dict] | None = None
    if filename.lower().endswith(".pdf"):
        try:
            raw_text, word_positions = extract_pdf_text_with_positions(content)
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=400, detail=f"Could not read PDF: {exc}") from exc
    else:
        raw_text = content.decode("utf-8", errors="ignore")

    invoice_id = uuid4()
    key = f"{invoice_id}/{filename}"
    file_path = storage.save(key, content, file.content_type or "application/pdf")

    extractor = get_extractor()
    classifier = get_classifier()
    log_buffer = BufferedLogFn()
    result = process_invoice(
        raw_text=raw_text,
        config=config,
        client_id=client_id,
        extractor=extractor,
        classifier=classifier,
        vendor_repository=vendor_repository,
        invoice_repository=repository,
        log_fn=log_buffer,
        invoice_id=invoice_id,
    )
    repository.save(result, file_path=file_path, raw_text=raw_text, client_id=client_id, word_positions=word_positions)
    log_buffer.flush_to(get_log_fn())

    payload = result.model_dump(mode="json")
    payload["file_path"] = file_path
    return payload


@app.get("/api/invoices/")
def list_invoices(
    status: str | None = None,
    needs_review: bool = False,
    vendor: str | None = None,
    repository: InvoiceRepository = Depends(get_repository),
    config: ClientConfig = Depends(get_active_config),
    client_id: str = Depends(get_client_id),
):
    invoices = repository.list(client_id)
    if status:
        invoices = [invoice for invoice in invoices if invoice.status.value == status]
    if needs_review:
        invoices = [invoice for invoice in invoices if _invoice_needs_review(invoice, config)]
    if vendor:
        vendor_lower = vendor.lower()
        invoices = [
            invoice
            for invoice in invoices
            if vendor_lower in str(invoice.extracted.vendor_name.value or "").lower()
        ]
    return [inv.model_dump(mode="json") for inv in invoices]


def _invoice_needs_review(invoice: ProcessedInvoice, config: ClientConfig) -> bool:
    if invoice.status not in {InvoiceStatus.review, InvoiceStatus.processing, InvoiceStatus.error}:
        return False
    if not invoice.validation.valid or invoice.enriched.duplicate:
        return True

    threshold = config.confidence_threshold
    for value in invoice.extracted.model_dump().values():
        if isinstance(value, dict) and value.get("value") not in {None, ""}:
            confidence = value.get("confidence")
            if isinstance(confidence, (int, float)) and confidence < threshold:
                return True
    return False


def _parse_invoice_id(invoice_id: str) -> UUID:
    try:
        return UUID(invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid invoice id") from exc


def _get_visible_invoice(invoice_id: str, repository: InvoiceRepository, client_id: str):
    parsed = _parse_invoice_id(invoice_id)
    invoice = repository.get(parsed, client_id)
    if invoice is None or invoice.status == InvoiceStatus.deleted:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return parsed, invoice


def _storage_key_from_file_path(file_path: str) -> str:
    if file_path.startswith("memory://"):
        return file_path.removeprefix("memory://")
    if file_path.startswith("supabase://"):
        return "/".join(file_path.split("/")[3:])
    raise HTTPException(status_code=404, detail="File not accessible")


def _rebuild_processed_invoice(
    invoice: ProcessedInvoice,
    extracted: ExtractedInvoice,
    repository: InvoiceRepository,
    vendor_repository: VendorRepository,
    config: ClientConfig,
    client_id: str,
) -> ProcessedInvoice:
    validation = validate_invoice(extracted, config)
    enriched = enrich_invoice(extracted, vendor_repository, repository, client_id)
    document_type = invoice.classification.document_type.value if invoice.classification else "invoice"
    formatted = format_invoice(enriched, config.output_connector, document_type)
    profile = detect_country(
        explicit_code=config.country_code,
        vendor_vat=extracted.vendor_vat.value if extracted.vendor_vat else None,
        currency=extracted.currency.value if extracted.currency else None,
    )
    return ProcessedInvoice(
        invoice_id=invoice.invoice_id,
        status=invoice.status,
        classification=invoice.classification,
        extracted=extracted,
        validation=validation,
        enriched=enriched,
        formatted=formatted,
        country_code=profile.code,
        file_path=invoice.file_path,
        raw_text=invoice.raw_text,
        word_positions=invoice.word_positions,
    )


@app.get("/api/invoices/{invoice_id}")
def get_invoice(
    invoice_id: str,
    repository: InvoiceRepository = Depends(get_repository),
    client_id: str = Depends(get_client_id),
):
    _, invoice = _get_visible_invoice(invoice_id, repository, client_id)
    return invoice.model_dump(mode="json")


@app.put("/api/invoices/{invoice_id}/approve")
def approve_invoice(
    invoice_id: str,
    repository: InvoiceRepository = Depends(get_repository),
    vendor_repository: VendorRepository = Depends(get_vendor_repository),
    client_id: str = Depends(get_client_id),
):
    parsed, invoice = _get_visible_invoice(invoice_id, repository, client_id)
    if not invoice.validation.valid:
        raise HTTPException(status_code=422, detail="Cannot approve invoice with validation errors")

    _learn_vendor_from_invoice(invoice, vendor_repository, client_id)
    repository.update_status(parsed, InvoiceStatus.approved, client_id)
    updated = repository.get(parsed, client_id)
    return updated.model_dump(mode="json")


def _learn_vendor_from_invoice(
    invoice: ProcessedInvoice, vendor_repository: VendorRepository, client_id: str
) -> None:
    extracted = invoice.extracted
    vendor_name = extracted.vendor_name.value if extracted.vendor_name else None
    vendor_vat = extracted.vendor_vat.value if extracted.vendor_vat else None
    vendor_iban = extracted.vendor_iban.value if extracted.vendor_iban else None
    if not vendor_name:
        return

    existing = vendor_repository.find_by_vat(str(vendor_vat), client_id) if vendor_vat else None
    if existing is None:
        existing = vendor_repository.find_by_name(str(vendor_name), client_id)
    if existing is not None:
        return

    vendor_repository.create(
        VendorCreate(
            name=str(vendor_name),
            vat_number=str(vendor_vat) if vendor_vat else None,
            iban=str(vendor_iban) if vendor_iban else None,
            category=invoice.enriched.category,
            metadata={"source_invoice_id": str(invoice.invoice_id)},
        ),
        client_id,
    )


@app.delete("/api/invoices/{invoice_id}", status_code=204)
def delete_invoice(
    invoice_id: str,
    repository: InvoiceRepository = Depends(get_repository),
    client_id: str = Depends(get_client_id),
):
    parsed = _parse_invoice_id(invoice_id)

    found = repository.update_status(parsed, InvoiceStatus.deleted, client_id)
    if not found:
        raise HTTPException(status_code=404, detail="Invoice not found")


_NUMERIC_FIELDS = {"subtotal", "vat_amount", "total_amount"}


def _coerce_field_value(field: str, value: Any) -> Any:
    if value == "":
        return None
    if field in _NUMERIC_FIELDS and isinstance(value, str):
        return float(value.replace(" ", "").replace(",", "."))
    return value


@app.put("/api/invoices/{invoice_id}/fields")
def update_invoice_fields(
    invoice_id: str,
    fields: dict[str, Any],
    repository: InvoiceRepository = Depends(get_repository),
    vendor_repository: VendorRepository = Depends(get_vendor_repository),
    config: ClientConfig = Depends(get_active_config),
    client_id: str = Depends(get_client_id),
):
    _, invoice = _get_visible_invoice(invoice_id, repository, client_id)
    extracted = invoice.extracted.model_copy(deep=True)

    for field, value in fields.items():
        if field not in ExtractedInvoice.model_fields:
            raise HTTPException(status_code=400, detail=f"Unsupported field: {field}")
        current = getattr(extracted, field)
        if not isinstance(current, ConfidenceValue):
            raise HTTPException(status_code=400, detail=f"Field is not editable: {field}")
        setattr(
            extracted,
            field,
            ConfidenceValue(value=_coerce_field_value(field, value), confidence=1.0),
        )

    updated = _rebuild_processed_invoice(invoice, extracted, repository, vendor_repository, config, client_id)
    saved = repository.save(
        updated,
        file_path=invoice.file_path or "",
        raw_text=invoice.raw_text or "",
        client_id=client_id,
        word_positions=invoice.word_positions,
    )
    return saved.model_dump(mode="json")


@app.post("/api/invoices/{invoice_id}/reprocess")
async def reprocess_invoice(
    invoice_id: str,
    force_ocr: bool = False,
    force_invoice: bool = False,
    repository: InvoiceRepository = Depends(get_repository),
    vendor_repository: VendorRepository = Depends(get_vendor_repository),
    storage: FileStorage = Depends(get_storage),
    config: ClientConfig = Depends(get_active_config),
    client_id: str = Depends(get_client_id),
):
    """Re-run the extraction pipeline on an already-uploaded invoice."""
    parsed, invoice = _get_visible_invoice(invoice_id, repository, client_id)
    raw_text = invoice.raw_text
    word_positions = invoice.word_positions

    if force_ocr:
        if not invoice.file_path:
            raise HTTPException(status_code=400, detail="No source file stored — cannot OCR")
        key = _storage_key_from_file_path(invoice.file_path)
        try:
            content = storage.read(key)
            raw_text, word_positions = extract_pdf_text_with_positions(content, force_ocr=True)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not OCR source PDF: {exc}") from exc

    if not raw_text:
        raise HTTPException(status_code=400, detail="No raw text stored — cannot reprocess")

    extractor = get_extractor()
    classifier = get_classifier()
    if force_invoice:
        # Manual override: the user says this IS an invoice. Keep the classifier's
        # party/reasoning output but force the type so extraction always runs.
        inner = classifier or classify_document

        def classifier(text: str) -> Classification:
            try:
                base = inner(text)
            except Exception:
                base = classify_document(text)
            reasoning = "Manually overridden to invoice by reviewer."
            if base.type_reasoning:
                reasoning = f"{reasoning} (Classifier said: {base.type_reasoning})"
            return base.model_copy(
                update={"document_type": DocumentType.invoice, "type_reasoning": reasoning}
            )

    result = process_invoice(
        raw_text=raw_text,
        config=config,
        client_id=client_id,
        extractor=extractor,
        classifier=classifier,
        vendor_repository=vendor_repository,
        invoice_repository=repository,
        log_fn=get_log_fn(),
        invoice_id=parsed,
    )
    repository.save(
        result,
        file_path=invoice.file_path or "",
        raw_text=raw_text,
        client_id=client_id,
        word_positions=word_positions,
    )
    payload = result.model_dump(mode="json")
    payload["file_path"] = invoice.file_path
    payload["raw_text"] = raw_text
    payload["word_positions"] = word_positions
    return payload


@app.get("/api/invoices/{invoice_id}/file")
def get_invoice_file(
    invoice_id: str,
    repository: InvoiceRepository = Depends(get_repository),
    storage: FileStorage = Depends(get_storage),
    client_id: str = Depends(get_client_id),
):
    _, invoice = _get_visible_invoice(invoice_id, repository, client_id)
    if not invoice.file_path:
        raise HTTPException(status_code=404, detail="No file stored for this invoice")

    file_path = invoice.file_path

    # Supabase storage: generate a signed URL and redirect
    if file_path.startswith("supabase://") and hasattr(storage, "get_url"):
        # strip "supabase://<bucket>/" prefix to get just the object key
        # file_path = "supabase://<bucket>/<key>" → split gives ["supabase:", "", "<bucket>", ...]
        key = "/".join(file_path.split("/")[3:])
        try:
            signed_url = storage.get_url(key)
            return RedirectResponse(url=signed_url)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Could not generate file URL: {exc}") from exc

    raise HTTPException(status_code=404, detail="File not accessible")


@app.get("/api/export/{invoice_id}/preview")
def preview_export(
    invoice_id: str,
    repository: InvoiceRepository = Depends(get_repository),
    client_id: str = Depends(get_client_id),
):
    _, invoice = _get_visible_invoice(invoice_id, repository, client_id)
    return {
        "invoice_id": str(invoice.invoice_id),
        "status": invoice.status.value,
        "export": invoice.formatted,
    }


@app.post("/api/export/{invoice_id}")
def export_invoice(
    invoice_id: str,
    repository: InvoiceRepository = Depends(get_repository),
    config: ClientConfig = Depends(get_active_config),
    client_id: str = Depends(get_client_id),
):
    parsed, invoice = _get_visible_invoice(invoice_id, repository, client_id)
    if not invoice.validation.valid:
        raise HTTPException(status_code=422, detail="Cannot export invoice with validation errors")

    formatted = invoice.formatted
    delivered: bool | None = None
    if formatted.get("type") == "webhook":
        delivered = _dispatch_webhook(invoice, config)
        # For a webhook connector the delivery IS the export. If it could not be
        # delivered, do not mark the invoice exported and report the failure.
        if delivered is False:
            raise HTTPException(status_code=502, detail="Webhook delivery failed after retries")

    repository.update_status(parsed, InvoiceStatus.exported, client_id)
    response: dict[str, Any] = {
        "invoice_id": str(invoice.invoice_id),
        "status": InvoiceStatus.exported.value,
        "export": formatted,
    }
    if delivered is not None:
        response["webhook_delivered"] = delivered
    return response


_WEBHOOK_MAX_ATTEMPTS = 3


def _dispatch_webhook(invoice, config: ClientConfig) -> bool | None:
    """POST the invoice payload to the webhook URL from connector_config.

    Retries up to _WEBHOOK_MAX_ATTEMPTS times on network error. When a
    ``webhook_secret`` is configured the body is signed with HMAC-SHA256 and the
    digest is sent in the ``X-Factura-Signature`` header so the receiver can
    verify authenticity.

    Returns True when delivered, False when every attempt failed, and None when
    no webhook URL is configured (nothing to deliver).
    """
    import hashlib
    import hmac
    import json
    import logging
    import urllib.error
    import urllib.request

    url = config.connector_config.get("webhook_url") or config.connector_config.get("url")
    if not url:
        return None

    body = json.dumps(invoice.formatted.get("payload", {})).encode()
    headers = {"Content-Type": "application/json", "X-Factura-Invoice-Id": str(invoice.invoice_id)}

    secret = config.connector_config.get("webhook_secret")
    if secret:
        signature = hmac.new(str(secret).encode(), body, hashlib.sha256).hexdigest()
        headers["X-Factura-Signature"] = f"sha256={signature}"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    for attempt in range(1, _WEBHOOK_MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=10):
                return True
        except urllib.error.URLError as exc:
            logging.warning(
                "Webhook delivery failed for invoice %s (attempt %d/%d): %s",
                invoice.invoice_id, attempt, _WEBHOOK_MAX_ATTEMPTS, exc,
            )
    return False


@app.get("/api/vendors/")
def list_vendors(
    repository: VendorRepository = Depends(get_vendor_repository),
    client_id: str = Depends(get_client_id),
):
    vendors = repository.list(client_id)
    return [vendor.model_dump(mode="json") for vendor in vendors]


@app.post("/api/vendors/")
def create_vendor(
    vendor: VendorCreate,
    repository: VendorRepository = Depends(get_vendor_repository),
    client_id: str = Depends(get_client_id),
):
    return repository.create(vendor, client_id).model_dump(mode="json")


@app.delete("/api/vendors/{vendor_id}", status_code=204)
def delete_vendor(
    vendor_id: str,
    repository: VendorRepository = Depends(get_vendor_repository),
    client_id: str = Depends(get_client_id),
):
    parsed = _parse_invoice_id(vendor_id)
    found = repository.delete(parsed, client_id)
    if not found:
        raise HTTPException(status_code=404, detail="Vendor not found")


@app.get("/api/stats")
def get_stats(
    repository: InvoiceRepository = Depends(get_repository),
    client_id: str = Depends(get_client_id),
):
    import collections

    from app.deps import _get_supabase_client

    invoices = repository.list(client_id, limit=10_000)
    by_status: dict[str, int] = {}
    valid_count = 0
    for inv in invoices:
        by_status[inv.status.value] = by_status.get(inv.status.value, 0) + 1
        if inv.validation.valid:
            valid_count += 1
    total = len(invoices)

    hours_saved = round(total * 15 / 60, 1)
    accuracy_rate = round(valid_count / total, 2) if total > 0 else 0.0

    daily_counts: list[dict] = []
    agent_performance: list[dict] = []

    try:
        client = _get_supabase_client()
        if client is not None:
            # daily_counts — last 30 days with any invoice (scoped to this tenant)
            try:
                result = (
                    client.table("invoices")
                    .select("created_at")
                    .eq("client_id", client_id)
                    .execute()
                )
                date_counts: dict[str, int] = collections.defaultdict(int)
                for row in result.data or []:
                    created_at = row.get("created_at")
                    if created_at:
                        date_str = str(created_at)[:10]
                        date_counts[date_str] += 1
                daily_counts = [
                    {"date": d, "count": c}
                    for d, c in sorted(date_counts.items())
                ]
            except Exception:
                daily_counts = []

            # agent_performance — avg duration per pipeline agent
            try:
                result = client.table("processing_logs").select("agent_name,duration_ms").execute()
                agent_durations: dict[str, list[int]] = collections.defaultdict(list)
                for row in result.data or []:
                    agent_name = row.get("agent_name")
                    duration_ms = row.get("duration_ms")
                    if agent_name is not None and duration_ms is not None:
                        agent_durations[agent_name].append(duration_ms)
                pipeline_order = ["extract", "validate", "enrich", "format"]
                agent_performance = [
                    {"agent": agent, "avg_ms": int(sum(durations) / len(durations))}
                    for agent in pipeline_order
                    if (durations := agent_durations.get(agent))
                ]
            except Exception:
                agent_performance = []
    except Exception:
        pass

    return {
        "total": total,
        "by_status": by_status,
        "valid": valid_count,
        "invalid": total - valid_count,
        "hours_saved": hours_saved,
        "accuracy_rate": accuracy_rate,
        "daily_counts": daily_counts,
        "agent_performance": agent_performance,
    }


@app.get("/api/config")
def get_config(config: ClientConfig = Depends(get_active_config)):
    return config.model_dump(mode="json")


@app.put("/api/config")
def update_config(
    body: ClientConfig,
    client_id: str = Depends(get_client_id),
    config_repo: ConfigRepository = Depends(get_config_repository),
):
    _config_cache[client_id] = body
    config_repo.save(body, client_id)
    return body.model_dump(mode="json")


@app.get("/api/config/demo")
def demo_config():
    return ClientConfig().model_dump(mode="json")
