from fastapi import FastAPI, File, UploadFile

from app.models import ClientConfig
from app.services.pipeline import process_invoice

app = FastAPI(title="AI Invoice Processing API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/invoices/upload")
async def upload_invoice(file: UploadFile = File(...)):
    content = await file.read()
    raw_text = content.decode("utf-8", errors="ignore")
    result = process_invoice(raw_text=raw_text, config=ClientConfig())
    return result.model_dump(mode="json")


@app.get("/api/config/demo")
def demo_config():
    return ClientConfig().model_dump(mode="json")
