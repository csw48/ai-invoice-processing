from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.deps import get_extractor, get_repository, get_storage
from app.models import ClientConfig
from app.repositories import InvoiceRepository
from app.services.pdf import extract_pdf_text
from app.services.pipeline import process_invoice
from app.storage import FileStorage

app = FastAPI(title="AI Invoice Processing API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    filename = file.filename or "invoice.pdf"
    if filename.lower().endswith(".pdf"):
        try:
            raw_text = extract_pdf_text(content)
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=400, detail=f"Could not read PDF: {exc}") from exc
    else:
        raw_text = content.decode("utf-8", errors="ignore")

    key = f"{uuid4()}/{filename}"
    file_path = storage.save(key, content, file.content_type or "application/pdf")

    extractor = get_extractor()
    result = process_invoice(raw_text=raw_text, config=ClientConfig(), extractor=extractor)
    repository.save(result, file_path=file_path, raw_text=raw_text)

    payload = result.model_dump(mode="json")
    payload["file_path"] = file_path
    return payload


@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: str, repository: InvoiceRepository = Depends(get_repository)):
    from uuid import UUID

    try:
        parsed = UUID(invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid invoice id") from exc

    invoice = repository.get(parsed)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice.model_dump(mode="json")


@app.get("/api/config/demo")
def demo_config():
    return ClientConfig().model_dump(mode="json")
