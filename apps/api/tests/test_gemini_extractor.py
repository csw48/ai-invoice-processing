import json

from app.services.gemini_extractor import GeminiExtractor, parse_gemini_response


def test_parse_gemini_response_returns_extracted_invoice():
    payload = json.dumps({
        "vendor_name": {"value": "Firma Test s.r.o.", "confidence": 0.95},
        "vendor_vat": {"value": "SK1234567890", "confidence": 0.92},
        "vendor_iban": {"value": None, "confidence": 0.0},
        "invoice_number": {"value": "INV-2026-001", "confidence": 0.93},
        "invoice_date": {"value": "07.05.2026", "confidence": 0.9},
        "due_date": {"value": None, "confidence": 0.0},
        "subtotal": {"value": 100.0, "confidence": 0.91},
        "vat_amount": {"value": 20.0, "confidence": 0.91},
        "total_amount": {"value": 120.0, "confidence": 0.95},
        "currency": {"value": "EUR", "confidence": 0.9},
        "po_number": {"value": None, "confidence": 0.0},
        "cost_center": {"value": None, "confidence": 0.0},
        "recipient_name": {"value": "Odberateľ s.r.o.", "confidence": 0.88},
        "recipient_vat": {"value": "SK9876543210", "confidence": 0.85},
        "recipient_city": {"value": "Bratislava", "confidence": 0.8},
        "line_items": [{"description": "Service", "qty": 1, "unit_price": 100.0, "vat_rate": 0.2, "total": 120.0}],
    })

    extracted = parse_gemini_response(payload)

    assert extracted.vendor_name.value == "Firma Test s.r.o."
    assert extracted.vendor_vat.value == "SK1234567890"
    assert extracted.total_amount.value == 120.0
    assert extracted.line_items[0].total == 120.0
    assert extracted.recipient_name.value == "Odberateľ s.r.o."
    assert extracted.recipient_vat.value == "SK9876543210"
    # Missing recipient fields default cleanly.
    assert extracted.recipient_country.value is None


class _StubGeminiClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict]] = []

    def generate_invoice_json(self, model: str, prompt: str, schema: dict) -> str:
        self.calls.append((model, prompt, schema))
        return self.response


def test_gemini_extractor_uses_configured_model_and_returns_invoice():
    response = json.dumps({
        "vendor_name": {"value": "ACME", "confidence": 0.9},
        "vendor_vat": {"value": None, "confidence": 0.0},
        "vendor_iban": {"value": None, "confidence": 0.0},
        "invoice_number": {"value": "X-1", "confidence": 0.8},
        "invoice_date": {"value": None, "confidence": 0.0},
        "due_date": {"value": None, "confidence": 0.0},
        "subtotal": {"value": None, "confidence": 0.0},
        "vat_amount": {"value": None, "confidence": 0.0},
        "total_amount": {"value": None, "confidence": 0.0},
        "currency": {"value": "EUR", "confidence": 0.6},
        "po_number": {"value": None, "confidence": 0.0},
        "cost_center": {"value": None, "confidence": 0.0},
        "line_items": [],
    })
    stub = _StubGeminiClient(response=response)
    extractor = GeminiExtractor(client=stub, model="gemini-3.1-flash-lite-preview")

    result = extractor.extract("Some PDF text")

    assert stub.calls[0][0] == "gemini-3.1-flash-lite-preview"
    assert "Some PDF text" in stub.calls[0][1]
    assert result.vendor_name.value == "ACME"
    assert result.invoice_number.value == "X-1"


class _FlakyGeminiClient:
    def __init__(self, fail_models: set[str], success_response: str) -> None:
        self.fail_models = fail_models
        self.success_response = success_response
        self.calls: list[str] = []

    def generate_invoice_json(self, model: str, prompt: str, schema: dict) -> str:
        self.calls.append(model)
        if model in self.fail_models:
            raise RuntimeError(f"503 UNAVAILABLE for {model}")
        return self.success_response


def test_gemini_extractor_falls_back_when_primary_model_unavailable():
    response = json.dumps({
        "vendor_name": {"value": "ACME", "confidence": 0.9},
        "vendor_vat": {"value": None, "confidence": 0.0},
        "vendor_iban": {"value": None, "confidence": 0.0},
        "invoice_number": {"value": "X-1", "confidence": 0.8},
        "invoice_date": {"value": None, "confidence": 0.0},
        "due_date": {"value": None, "confidence": 0.0},
        "subtotal": {"value": None, "confidence": 0.0},
        "vat_amount": {"value": None, "confidence": 0.0},
        "total_amount": {"value": None, "confidence": 0.0},
        "currency": {"value": "EUR", "confidence": 0.6},
        "po_number": {"value": None, "confidence": 0.0},
        "cost_center": {"value": None, "confidence": 0.0},
        "line_items": [],
    })
    stub = _FlakyGeminiClient(
        fail_models={"gemini-3.1-flash-lite-preview"},
        success_response=response,
    )
    extractor = GeminiExtractor(
        client=stub,
        model="gemini-3.1-flash-lite-preview",
        fallback_models=["gemini-2.5-flash-lite"],
    )

    result = extractor.extract("Some PDF text")

    assert stub.calls == ["gemini-3.1-flash-lite-preview", "gemini-2.5-flash-lite"]
    assert result.vendor_name.value == "ACME"
