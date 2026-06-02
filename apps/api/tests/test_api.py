import json

import pymupdf
from fastapi.testclient import TestClient

from app.deps import set_classifier, set_config_repository, set_extractor, set_repository, set_storage, set_vendor_repository
from app.models import ClientConfig
import app.main as main_module
from app.main import app
from app.repositories import ConfigRepository, InMemoryInvoiceRepository, InMemoryVendorRepository
from app.services.classify import classify_document
from app.services.extract import extract_invoice_fields
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
    set_vendor_repository(InMemoryVendorRepository())
    set_extractor(extract_invoice_fields)
    set_classifier(classify_document)
    set_config_repository(ConfigRepository(None))
    main_module._config_cache = {}
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


def test_upload_saves_invoice_before_processing_logs_are_flushed(monkeypatch):
    client = _client()
    events: list[str] = []

    class TrackingInvoiceRepository(InMemoryInvoiceRepository):
        def save(self, *args, **kwargs):
            events.append("save")
            return super().save(*args, **kwargs)

    def log(agent_name, input_data, output_data, duration_ms, error, invoice_id=None):
        events.append(f"log:{agent_name}")

    set_repository(TrackingInvoiceRepository())
    monkeypatch.setattr(main_module, "get_log_fn", lambda: log)
    pdf_bytes = _pdf_with(
        "Firma Test s.r.o.\n"
        "VAT: SK1234567890\n"
        "Invoice number: INV-2026-LOG\n"
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
    assert events == [
        "save",
        "log:classify",
        "log:extract",
        "log:validate",
        "log:enrich",
        "log:format",
    ]


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


def test_list_invoices_can_filter_review_queue():
    client = _client()
    valid_pdf = _pdf_with(
        "Firma Valid s.r.o.\n"
        "VAT: SK1234567890\n"
        "Invoice number: INV-VALID\n"
        "Invoice date: 07.05.2026\n"
        "Subtotal: 100.00\n"
        "VAT: 20.00\n"
        "Total: 120.00 EUR\n"
    )
    invalid_pdf = _pdf_with(
        "Firma Missing Date s.r.o.\n"
        "VAT: SK1234567890\n"
        "Invoice number: INV-REVIEW\n"
        "Total: 120.00 EUR\n"
    )
    client.post("/api/invoices/upload", files={"file": ("valid.pdf", valid_pdf, "application/pdf")})
    client.post("/api/invoices/upload", files={"file": ("invalid.pdf", invalid_pdf, "application/pdf")})

    response = client.get("/api/invoices/?needs_review=true")

    assert response.status_code == 200
    invoices = response.json()
    assert [inv["extracted"]["invoice_number"]["value"] for inv in invoices] == ["INV-REVIEW"]


def test_reprocess_can_force_ocr_from_original_file(monkeypatch):
    client = _client()
    pdf_bytes = _pdf_with("Firma Test s.r.o.\nInvoice number: INV-TEXT-ONLY\n")
    upload = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    invoice_id = upload.json()["invoice_id"]

    def fake_extract(content: bytes, force_ocr: bool = False):
        if force_ocr:
            return "OCR Firma s.r.o.\nInvoice number: INV-FORCED-OCR\nTotal: 120.00 EUR", []
        return "SHOULD NOT USE NORMAL EXTRACTION", []

    monkeypatch.setattr(main_module, "extract_pdf_text_with_positions", fake_extract)

    response = client.post(f"/api/invoices/{invoice_id}/reprocess?force_ocr=true")

    assert response.status_code == 200
    body = response.json()
    assert body["raw_text"].startswith("OCR Firma")
    assert body["extracted"]["invoice_number"]["value"] == "INV-FORCED-OCR"


def test_update_invoice_fields_revalidates_and_reformats_invoice():
    client = _client()
    pdf_bytes = _pdf_with(
        "Firma Test s.r.o.\n"
        "VAT: SK1234567890\n"
        "Invoice number: INV-EDIT-001\n"
        "Invoice date: 07.05.2026\n"
        "Subtotal: 100.00\n"
        "VAT: 20.00\n"
        "Total: 121.00 EUR\n"
    )
    upload = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    invoice_id = upload.json()["invoice_id"]
    assert upload.json()["validation"]["valid"] is False

    response = client.put(
        f"/api/invoices/{invoice_id}/fields",
        json={"total_amount": 120.0, "vendor_name": "Corrected Vendor s.r.o."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["valid"] is True
    assert body["extracted"]["total_amount"]["value"] == 120.0
    assert body["extracted"]["total_amount"]["confidence"] == 1.0
    assert body["extracted"]["vendor_name"]["value"] == "Corrected Vendor s.r.o."
    assert body["formatted"]["payload"]["total_amount"]["value"] == 120.0


def test_get_invoice_returns_404_for_unknown_id():
    client = _client()

    response = client.get("/api/invoices/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_export_preview_returns_formatted_payload():
    client = _client()
    pdf_bytes = _pdf_with(
        "Firma Test s.r.o.\n"
        "Invoice number: INV-2026-003\n"
        "Invoice date: 07.05.2026\n"
        "Total: 120.00 EUR\n"
    )
    upload = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    invoice_id = upload.json()["invoice_id"]

    response = client.get(f"/api/export/{invoice_id}/preview")

    assert response.status_code == 200
    body = response.json()
    assert body["invoice_id"] == invoice_id
    assert body["export"]["type"] == "json"
    assert body["export"]["payload"]["invoice_number"]["value"] == "INV-2026-003"


def test_export_marks_valid_invoice_as_exported():
    client = _client()
    pdf_bytes = _pdf_with(
        "Firma Test s.r.o.\n"
        "VAT: SK1234567890\n"
        "Invoice number: INV-2026-004\n"
        "Invoice date: 07.05.2026\n"
        "Subtotal: 100.00\n"
        "VAT: 20.00\n"
        "Total: 120.00 EUR\n"
    )
    upload = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    invoice_id = upload.json()["invoice_id"]

    response = client.post(f"/api/export/{invoice_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["invoice_id"] == invoice_id
    assert body["status"] == "exported"
    assert body["export"]["type"] == "json"


def test_approve_learns_new_vendor_from_invoice():
    client = _client()
    vendor_repository = InMemoryVendorRepository()
    set_vendor_repository(vendor_repository)
    pdf_bytes = _pdf_with(
        "Novy Dodavatel s.r.o.\n"
        "VAT: SK1234567890\n"
        "IBAN: SK3112000000198742637541\n"
        "Invoice number: INV-LEARN-001\n"
        "Invoice date: 07.05.2026\n"
        "Subtotal: 100.00\n"
        "VAT: 20.00\n"
        "Total: 120.00 EUR\n"
    )
    upload = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    invoice_id = upload.json()["invoice_id"]

    response = client.put(f"/api/invoices/{invoice_id}/approve")

    assert response.status_code == 200
    vendor = vendor_repository.find_by_vat("SK1234567890", "default")
    assert vendor is not None
    assert vendor.name == "Novy Dodavatel s.r.o."
    assert vendor.iban == "SK3112000000198742637541"
    assert vendor.metadata["source_invoice_id"] == invoice_id


def test_export_rejects_invoice_with_validation_errors():
    client = _client()
    pdf_bytes = _pdf_with("Firma Test s.r.o.\nInvoice number: INV-2026-005\n")
    upload = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    invoice_id = upload.json()["invoice_id"]

    response = client.post(f"/api/export/{invoice_id}")

    assert response.status_code == 422


def test_export_webhook_uses_active_connector_config(monkeypatch):
    client = _client()
    main_module._config_cache = {
        ConfigRepository.DEFAULT_ID: ClientConfig(
            output_connector="webhook",
            connector_config={"webhook_url": "https://example.test/invoice-webhook"},
        )
    }
    sent_requests: list[tuple[str, bytes | None, dict]] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout):
        sent_requests.append((request.full_url, request.data, dict(request.headers)))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    pdf_bytes = _pdf_with(
        "Firma Test s.r.o.\n"
        "VAT: SK1234567890\n"
        "Invoice number: INV-2026-WEBHOOK\n"
        "Invoice date: 07.05.2026\n"
        "Subtotal: 100.00\n"
        "VAT: 20.00\n"
        "Total: 120.00 EUR\n"
    )
    upload = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    invoice_id = upload.json()["invoice_id"]

    response = client.post(f"/api/export/{invoice_id}")

    assert response.status_code == 200
    assert len(sent_requests) == 1
    url, body, headers = sent_requests[0]
    assert url == "https://example.test/invoice-webhook"
    assert headers["X-factura-invoice-id"] == invoice_id
    payload = json.loads((body or b"{}").decode())
    assert payload["invoice_number"]["value"] == "INV-2026-WEBHOOK"


def test_export_webhook_retries_on_failure(monkeypatch):
    import urllib.error

    client = _client()
    main_module._config_cache = {
        ConfigRepository.DEFAULT_ID: ClientConfig(
            output_connector="webhook",
            connector_config={"webhook_url": "https://example.test/invoice-webhook"},
        )
    }
    attempts: list[int] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def flaky_urlopen(request, timeout):
        attempts.append(1)
        if len(attempts) < 3:
            raise urllib.error.URLError("connection refused")
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", flaky_urlopen)
    pdf_bytes = _pdf_with(
        "Firma Test s.r.o.\n"
        "VAT: SK1234567890\n"
        "Invoice number: INV-2026-RETRY\n"
        "Invoice date: 07.05.2026\n"
        "Subtotal: 100.00\n"
        "VAT: 20.00\n"
        "Total: 120.00 EUR\n"
    )
    upload = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    invoice_id = upload.json()["invoice_id"]

    response = client.post(f"/api/export/{invoice_id}")

    assert response.status_code == 200
    assert len(attempts) == 3  # failed twice, succeeded on the third
    assert response.json()["webhook_delivered"] is True


def test_export_webhook_signs_body_with_hmac_when_secret_set(monkeypatch):
    import hashlib
    import hmac

    client = _client()
    secret = "s3cr3t"
    main_module._config_cache = {
        ConfigRepository.DEFAULT_ID: ClientConfig(
            output_connector="webhook",
            connector_config={"webhook_url": "https://example.test/hook", "webhook_secret": secret},
        )
    }
    captured: list[tuple[bytes, dict]] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout):
        captured.append((request.data, dict(request.headers)))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    pdf_bytes = _pdf_with(
        "Firma Test s.r.o.\nVAT: SK1234567890\nInvoice number: INV-HMAC\n"
        "Invoice date: 07.05.2026\nSubtotal: 100.00\nVAT: 20.00\nTotal: 120.00 EUR\n"
    )
    invoice_id = client.post(
        "/api/invoices/upload", files={"file": ("i.pdf", pdf_bytes, "application/pdf")}
    ).json()["invoice_id"]

    response = client.post(f"/api/export/{invoice_id}")

    assert response.status_code == 200
    body, headers = captured[0]
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert headers["X-factura-signature"] == expected


def test_export_webhook_permanent_failure_does_not_mark_exported(monkeypatch):
    import urllib.error

    client = _client()
    main_module._config_cache = {
        ConfigRepository.DEFAULT_ID: ClientConfig(
            output_connector="webhook",
            connector_config={"webhook_url": "https://example.test/hook"},
        )
    }

    def always_fail(request, timeout):
        raise urllib.error.URLError("down")

    monkeypatch.setattr("urllib.request.urlopen", always_fail)
    pdf_bytes = _pdf_with(
        "Firma Test s.r.o.\nVAT: SK1234567890\nInvoice number: INV-FAIL\n"
        "Invoice date: 07.05.2026\nSubtotal: 100.00\nVAT: 20.00\nTotal: 120.00 EUR\n"
    )
    invoice_id = client.post(
        "/api/invoices/upload", files={"file": ("i.pdf", pdf_bytes, "application/pdf")}
    ).json()["invoice_id"]

    response = client.post(f"/api/export/{invoice_id}")
    assert response.status_code == 502

    # Invoice must NOT be marked exported — delivery is the export for a webhook.
    fetched = client.get(f"/api/invoices/{invoice_id}").json()
    assert fetched["status"] != "exported"


def test_vendor_crud_lists_created_vendor_and_soft_deletes_it():
    client = _client()

    create = client.post(
        "/api/vendors/",
        json={
            "name": "Acme Slovakia s.r.o.",
            "vat_number": "SK1234567890",
            "iban": "SK8975000000000012345678",
            "category": "software",
            "metadata": {"default_cost_center": "IT"},
        },
    )

    assert create.status_code == 200
    vendor = create.json()
    assert vendor["name"] == "Acme Slovakia s.r.o."
    assert vendor["metadata"]["default_cost_center"] == "IT"

    list_response = client.get("/api/vendors/")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [vendor["id"]]

    delete = client.delete(f"/api/vendors/{vendor['id']}")
    assert delete.status_code == 204

    list_after_delete = client.get("/api/vendors/")
    assert list_after_delete.status_code == 200
    assert list_after_delete.json() == []


def test_upload_rejects_empty_file():
    client = _client()

    response = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400


def test_config_is_isolated_per_client():
    from app.auth import get_client_id

    client = _client()
    try:
        # Simulate two authenticated tenants via the verified-identity dependency.
        app.dependency_overrides[get_client_id] = lambda: "client-a"
        put = client.put(
            "/api/config",
            json=ClientConfig(name="Client A").model_dump(mode="json"),
        )
        assert put.status_code == 200
        assert client.get("/api/config").json()["name"] == "Client A"

        app.dependency_overrides[get_client_id] = lambda: "client-b"
        assert client.get("/api/config").json()["name"] != "Client A"
    finally:
        app.dependency_overrides.pop(get_client_id, None)


def test_unauthenticated_request_rejected_when_auth_enabled(monkeypatch):
    import app.auth as auth_module
    from app.core.config import Settings

    client = _client()
    monkeypatch.setattr(
        auth_module, "get_settings",
        lambda: Settings(enable_auth=True, clerk_jwks_url="https://example.test/jwks"),
    )

    # No bearer token → 401, regardless of any spoofed X-Client-Id header.
    resp = client.get(
        "/api/invoices/00000000-0000-0000-0000-000000000000",
        headers={"X-Client-Id": "victim"},
    )
    assert resp.status_code == 401


def test_tenant_derived_from_verified_token_not_header(monkeypatch):
    import app.auth as auth_module
    from app.core.config import Settings

    client = _client()
    monkeypatch.setattr(
        auth_module, "get_settings",
        lambda: Settings(enable_auth=True, clerk_jwks_url="https://example.test/jwks"),
    )
    monkeypatch.setattr(auth_module, "_verify_clerk_token", lambda token: {"org_id": "org_real"})

    headers = {"Authorization": "Bearer faketoken", "X-Client-Id": "org_spoofed"}
    put = client.put(
        "/api/config",
        json=ClientConfig(name="Real Org").model_dump(mode="json"),
        headers=headers,
    )
    assert put.status_code == 200

    # Tenant comes from the verified token (org_real), not the spoofed header.
    got = client.get("/api/config", headers=headers)
    assert got.json()["name"] == "Real Org"


def test_invoice_data_isolated_per_tenant():
    from app.auth import get_client_id

    client = _client()
    pdf_bytes = _pdf_with("Firma A s.r.o.\nInvoice number: INV-TENANT-A\nTotal: 120.00 EUR\n")
    try:
        app.dependency_overrides[get_client_id] = lambda: "tenant-a"
        upload = client.post(
            "/api/invoices/upload",
            files={"file": ("a.pdf", pdf_bytes, "application/pdf")},
        )
        invoice_id = upload.json()["invoice_id"]
        assert client.get(f"/api/invoices/{invoice_id}").status_code == 200
        assert len(client.get("/api/invoices/").json()) == 1

        # Tenant B cannot read tenant A's invoice, by id or in listings.
        app.dependency_overrides[get_client_id] = lambda: "tenant-b"
        assert client.get(f"/api/invoices/{invoice_id}").status_code == 404
        assert client.get("/api/invoices/").json() == []
        # Nor delete it.
        assert client.delete(f"/api/invoices/{invoice_id}").status_code == 404
    finally:
        app.dependency_overrides.pop(get_client_id, None)


def test_vendor_data_isolated_per_tenant():
    from app.auth import get_client_id

    client = _client()
    try:
        app.dependency_overrides[get_client_id] = lambda: "tenant-a"
        created = client.post("/api/vendors/", json={"name": "Acme A", "vat_number": "SK1111111111"})
        vendor_id = created.json()["id"]
        assert len(client.get("/api/vendors/").json()) == 1

        app.dependency_overrides[get_client_id] = lambda: "tenant-b"
        assert client.get("/api/vendors/").json() == []
        assert client.delete(f"/api/vendors/{vendor_id}").status_code == 404
    finally:
        app.dependency_overrides.pop(get_client_id, None)
