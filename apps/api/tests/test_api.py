import pymupdf
from fastapi.testclient import TestClient

from app.deps import set_repository, set_storage
from app.main import app
from app.repositories import InMemoryInvoiceRepository
from app.storage import InMemoryFileStorage


def _pdf_with(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    for index, line in enumerate(text.splitlines()):
        page.insert_text((50, 72 + index * 14), line)
    return doc.tobytes()


def _client():
    set_storage(InMemoryFileStorage())
    set_repository(InMemoryInvoiceRepository())
    return TestClient(app)


def test_upload_pdf_returns_invoice_with_extracted_fields():
    client = _client()
    pdf_bytes = _pdf_with(
        "Firma Test s.r.o.\n"
        "VAT: SK1234567890\n"
        "Invoice number: INV-2026-001\n"
        "Invoice date: 07.05.2026\n"
        "Subtotal: 100.00\n"
        "VAT: 20.00\n"
        "Total: 120.00 EUR\n"
    )

    response = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["extracted"]["invoice_number"]["value"] == "INV-2026-001"
    assert body["file_path"].startswith("memory://")


def test_get_invoice_returns_saved_record():
    client = _client()
    pdf_bytes = _pdf_with("Firma Test s.r.o.\nInvoice number: INV-2026-002\n")
    upload = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    invoice_id = upload.json()["invoice_id"]

    response = client.get(f"/api/invoices/{invoice_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["invoice_id"] == invoice_id
    assert body["extracted"]["invoice_number"]["value"] == "INV-2026-002"


def test_get_invoice_returns_404_for_unknown_id():
    client = _client()

    response = client.get("/api/invoices/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_upload_rejects_empty_file():
    client = _client()

    response = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
