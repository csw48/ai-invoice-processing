from app.repositories import InMemoryInvoiceRepository, InvoiceRepository
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
