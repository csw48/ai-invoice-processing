import os

from app.repositories import InMemoryInvoiceRepository, InvoiceRepository
from app.services.extract import extract_invoice_fields
from app.storage import FileStorage, InMemoryFileStorage

_storage: FileStorage = InMemoryFileStorage()
_repository: InvoiceRepository = InMemoryInvoiceRepository()


def get_storage() -> FileStorage:
    return _storage


def get_repository() -> InvoiceRepository:
    return _repository


def set_storage(storage: FileStorage) -> None:
    global _storage
    _storage = storage


def set_repository(repository: InvoiceRepository) -> None:
    global _repository
    _repository = repository


_extractor = None


def get_extractor():
    """Return an extractor callable. Uses Gemini if GEMINI_API_KEY is set,
    otherwise the deterministic regex extractor.

    The callable signature is: (raw_text: str) -> ExtractedInvoice.
    """
    global _extractor
    if _extractor is not None:
        return _extractor

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
            # Fall through to regex extractor on any setup error.
            pass

    _extractor = extract_invoice_fields
    return _extractor


def set_extractor(extractor) -> None:
    global _extractor
    _extractor = extractor
