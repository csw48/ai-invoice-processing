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

    upload = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 200
    # Upload returns a stub immediately (status=processing); background task
    # runs synchronously in TestClient before this call returns.
    invoice_id = upload.json()["invoice_id"]
    assert upload.json()["file_path"].startswith("memory://")

    body = client.get(f"/api/invoices/{invoice_id}").json()
    assert body["extracted"]["invoice_number"]["value"] == "INV-2026-001"


def test_upload_saves_invoice_before_processing_logs_are_flushed(monkeypatch):
    client = _client()
    events: list[str] = []

    class TrackingInvoiceRepository(InMemoryInvoiceRepository):
        def save(self, *args, **kwargs):
            events.append("save")
            return super().save(*args, **kwargs)

    def log(agent_name, input_data, output_data, duration_ms, error, invoice_id=None, client_id=None):
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
    # Stub is saved first, then background task: save full result + flush logs.
    assert events[:2] == ["save", "save"]
    assert events[2:] == [
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
    body = response.json()
    invoices = body["items"]
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
    # Background task runs synchronously in TestClient; fetch processed result.
    fetched = client.get(f"/api/invoices/{invoice_id}").json()
    assert fetched["validation"]["valid"] is False

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

    monkeypatch.setattr(main_module, "_resolve_host_ips", lambda host: ["93.184.216.34"])
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

    monkeypatch.setattr(main_module, "_resolve_host_ips", lambda host: ["93.184.216.34"])
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

    monkeypatch.setattr(main_module, "_resolve_host_ips", lambda host: ["93.184.216.34"])
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

    monkeypatch.setattr(main_module, "_resolve_host_ips", lambda host: ["93.184.216.34"])
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
        assert client.get("/api/invoices/").json()["total"] == 1

        # Tenant B cannot read tenant A's invoice, by id or in listings.
        app.dependency_overrides[get_client_id] = lambda: "tenant-b"
        assert client.get(f"/api/invoices/{invoice_id}").status_code == 404
        assert client.get("/api/invoices/").json()["items"] == []
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


def test_reprocess_force_invoice_overrides_classification():
    client = _client()
    # Too short / no markers → deterministic classifier diverts to junk.
    pdf_bytes = _pdf_with("Hello world")
    upload = client.post(
        "/api/invoices/upload",
        files={"file": ("scan.pdf", pdf_bytes, "application/pdf")},
    )
    invoice_id = upload.json()["invoice_id"]
    body = client.get(f"/api/invoices/{invoice_id}").json()
    assert body["classification"]["document_type"] == "junk"
    assert body["status"] == "discarded"

    response = client.post(f"/api/invoices/{invoice_id}/reprocess?force_invoice=true")

    assert response.status_code == 200
    body = response.json()
    assert body["classification"]["document_type"] == "invoice"
    assert "overridden" in body["classification"]["type_reasoning"]
    # Extraction pipeline ran (no longer short-circuited).
    assert body["status"] != "discarded"
    assert body["formatted"]["type"] != "skipped"


def test_field_edits_are_tracked_and_feed_stats():
    client = _client()
    pdf_bytes = _pdf_with(
        "Firma Test s.r.o.\n"
        "VAT: SK1234567890\n"
        "Invoice number: INV-TRACK-001\n"
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
    assert upload.json()["edited_fields"] == []

    # Edit two fields; resubmitting an unchanged value must not count as an edit.
    response = client.put(
        f"/api/invoices/{invoice_id}/fields",
        json={
            "total_amount": 125.0,
            "vendor_name": "Corrected Vendor s.r.o.",
            "invoice_number": "INV-TRACK-001",  # unchanged
        },
    )
    assert response.status_code == 200
    assert sorted(response.json()["edited_fields"]) == ["total_amount", "vendor_name"]

    # A second edit of the same field is not double-counted.
    response = client.put(
        f"/api/invoices/{invoice_id}/fields",
        json={"total_amount": 120.0},
    )
    assert sorted(response.json()["edited_fields"]) == ["total_amount", "vendor_name"]

    stats = client.get("/api/stats").json()
    assert stats["extraction_accuracy"] == 0.0  # 1 of 1 extracted invoices edited
    corrections = {c["field"]: c for c in stats["field_corrections"]}
    assert corrections["total_amount"]["count"] == 1
    assert corrections["vendor_name"]["count"] == 1
    assert corrections["total_amount"]["rate"] == 1.0


def test_approve_backfills_missing_vendor_details():
    client = _client()
    # Seed a vendor known only by name — no VAT, no IBAN stored.
    seeded = client.post(
        "/api/vendors/",
        json={"name": "Firma Test s.r.o.", "category": "services"},
    ).json()

    pdf_bytes = _pdf_with(
        "Firma Test s.r.o.\n"
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

    approve = client.put(f"/api/invoices/{invoice_id}/approve")
    assert approve.status_code == 200

    vendors = client.get("/api/vendors/").json()
    assert len(vendors) == 1  # backfilled, not duplicated
    vendor = vendors[0]
    assert vendor["id"] == seeded["id"]
    assert vendor["vat_number"] == "SK1234567890"
    assert vendor["iban"] == "SK3112000000198742637541"


def test_export_webhook_blocks_non_public_urls(monkeypatch):
    """SSRF guard: file://, loopback and link-local targets are rejected with 422."""
    client = _client()
    # Webhook connector must be active at upload time so the invoice formats as webhook.
    main_module._config_cache = {
        ConfigRepository.DEFAULT_ID: ClientConfig(
            output_connector="webhook",
            connector_config={"webhook_url": "https://example.test/hook"},
        )
    }
    pdf_bytes = _pdf_with(
        "Firma Test s.r.o.\n"
        "VAT: SK1234567890\n"
        "Invoice number: INV-2026-SSRF\n"
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

    def attempt(url: str):
        main_module._config_cache = {
            ConfigRepository.DEFAULT_ID: ClientConfig(
                output_connector="webhook",
                connector_config={"webhook_url": url},
            )
        }
        return client.post(f"/api/export/{invoice_id}")

    calls: list[str] = []
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout: calls.append(req.full_url),
    )

    for url in (
        "file:///etc/passwd",
        "ftp://example.test/x",
        "http://127.0.0.1:8000/api/config",
        "http://localhost/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/internal",
        "http://192.168.1.1/",
    ):
        response = attempt(url)
        assert response.status_code == 422, url
        assert "public http(s)" in response.json()["detail"]
    assert calls == []  # no request ever left the building


def test_csv_export_neutralizes_formula_injection():
    from app.models import ConfidenceValue
    from app.services.extract import extract_invoice_fields

    extracted = extract_invoice_fields(
        "Firma Test s.r.o.\nInvoice number: INV-1\nTotal: 120.00 EUR\n"
    )
    extracted.vendor_name = ConfidenceValue(value="=cmd|'/c calc'!A1", confidence=0.9)
    extracted.subtotal = ConfidenceValue(value=-100.0, confidence=0.9)  # credit note

    from app.models import EnrichedInvoice
    from app.services.formatters import format_invoice

    csv_payload = format_invoice(EnrichedInvoice(extracted=extracted), "csv")["payload"]
    data_row = csv_payload.splitlines()[1]
    assert "'=cmd" in data_row  # formula neutralized
    assert "'-100" not in data_row and "-100" in data_row  # numbers untouched


def test_upload_filename_cannot_traverse_storage_prefix():
    client = _client()
    pdf_bytes = _pdf_with("Firma Test s.r.o.\nInvoice number: INV-1\nTotal: 120.00 EUR\n")
    response = client.post(
        "/api/invoices/upload",
        files={"file": ("../../other-tenant/evil.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    file_path = response.json()["file_path"]
    assert ".." not in file_path
    assert file_path.endswith("/evil.pdf")
