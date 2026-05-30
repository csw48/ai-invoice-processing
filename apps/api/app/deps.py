import os

from app.repositories import (
    ConfigRepository,
    InMemoryInvoiceRepository,
    InMemoryVendorRepository,
    InvoiceRepository,
    VendorRepository,
)
from app.services.extract import extract_invoice_fields
from app.storage import FileStorage, InMemoryFileStorage

_storage: FileStorage | None = None
_repository: InvoiceRepository | None = None
_vendor_repository: VendorRepository | None = None
_config_repository: ConfigRepository | None = None
_supabase_client = None


def _get_supabase_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    from app.core.config import get_settings
    settings = get_settings()
    if settings.supabase_url and settings.supabase_service_role_key:
        from supabase import create_client
        _supabase_client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _supabase_client


def get_storage() -> FileStorage:
    global _storage
    if _storage is not None:
        return _storage
    client = _get_supabase_client()
    if client:
        from app.core.config import get_settings
        from app.storage import SupabaseFileStorage
        _storage = SupabaseFileStorage(client, get_settings().supabase_storage_bucket)
    else:
        _storage = InMemoryFileStorage()
    return _storage


def get_repository() -> InvoiceRepository:
    global _repository
    if _repository is not None:
        return _repository
    client = _get_supabase_client()
    if client:
        from app.repositories import SupabaseInvoiceRepository
        _repository = SupabaseInvoiceRepository(client)
    else:
        _repository = InMemoryInvoiceRepository()
    return _repository


def get_vendor_repository() -> VendorRepository:
    global _vendor_repository
    if _vendor_repository is not None:
        return _vendor_repository
    client = _get_supabase_client()
    if client:
        from app.repositories import SupabaseVendorRepository
        _vendor_repository = SupabaseVendorRepository(client)
    else:
        _vendor_repository = InMemoryVendorRepository()
    return _vendor_repository


def set_storage(storage: FileStorage) -> None:
    global _storage
    _storage = storage


def set_repository(repository: InvoiceRepository) -> None:
    global _repository
    _repository = repository


def set_vendor_repository(repository: VendorRepository) -> None:
    global _vendor_repository
    _vendor_repository = repository


def get_config_repository() -> ConfigRepository:
    global _config_repository
    if _config_repository is not None:
        return _config_repository
    client = _get_supabase_client()
    _config_repository = ConfigRepository(client)
    return _config_repository


def set_config_repository(repository: ConfigRepository) -> None:
    global _config_repository
    _config_repository = repository


_extractor = None


def get_extractor():
    """Return an extractor callable.

    Priority:
      1. LOCAL_LLM_URL is set → local LLM via OpenAI-compatible API (LM Studio / Ollama)
      2. GEMINI_API_KEY is set → Gemini
      3. Fallback → deterministic regex extractor

    The callable signature is: (raw_text: str) -> ExtractedInvoice.
    """
    global _extractor
    if _extractor is not None:
        return _extractor

    local_url = os.getenv("LOCAL_LLM_URL", "").strip()
    if local_url:
        try:
            from app.services.local_extractor import LocalLLMExtractor
            model = os.getenv("LOCAL_LLM_MODEL", "local-model")
            llm_api_key = os.getenv("LOCAL_LLM_API_KEY", "lm-studio")
            _extractor = LocalLLMExtractor(base_url=local_url, model=model, api_key=llm_api_key).extract
            return _extractor
        except Exception:
            pass

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            from app.services.gemini_extractor import GeminiExtractor, RealGeminiClient
            primary = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
            fallback_csv = os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash-lite")
            fallbacks = [m.strip() for m in fallback_csv.split(",") if m.strip()]
            client = RealGeminiClient(api_key=api_key)
            gemini = GeminiExtractor(client=client, model=primary, fallback_models=fallbacks)
            _extractor = gemini.extract
            return _extractor
        except Exception:
            pass

    _extractor = extract_invoice_fields
    return _extractor


def set_extractor(extractor) -> None:
    global _extractor
    _extractor = extractor


_classifier = None


def get_classifier():
    """Return a classifier callable: (raw_text: str) -> Classification.

    Uses the same LLM as the extractor (Gemini) when GEMINI_API_KEY is set,
    otherwise falls back to the deterministic classifier.
    """
    global _classifier
    if _classifier is not None:
        return _classifier

    from app.services.classify import classify_document

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            from app.services.classify import GeminiClassifier
            from app.services.gemini_extractor import RealGeminiClient
            primary = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
            fallback_csv = os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash-lite")
            fallbacks = [m.strip() for m in fallback_csv.split(",") if m.strip()]
            client = RealGeminiClient(api_key=api_key)
            _classifier = GeminiClassifier(client=client, model=primary, fallback_models=fallbacks).classify
            return _classifier
        except Exception:
            pass

    _classifier = classify_document
    return _classifier


def set_classifier(classifier) -> None:
    global _classifier
    _classifier = classifier


def get_log_fn():
    """Return a log function if Supabase is configured, else None."""
    from app.services.log import make_logger
    return make_logger(_get_supabase_client())
