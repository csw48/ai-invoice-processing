from typing import Protocol


class FileStorage(Protocol):
    """Stores raw uploaded invoice files (PDFs)."""

    def save(self, key: str, content: bytes, content_type: str = "application/pdf") -> str:
        """Persist the file and return its path/URL."""
        ...


class InMemoryFileStorage:
    """In-memory implementation used by tests and local development."""

    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}

    def save(self, key: str, content: bytes, content_type: str = "application/pdf") -> str:
        self._files[key] = content
        return f"memory://{key}"

    def read(self, key: str) -> bytes:
        return self._files[key]


class SupabaseFileStorage:
    """Supabase Storage implementation; only constructed when env vars are configured."""

    def __init__(self, client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def save(self, key: str, content: bytes, content_type: str = "application/pdf") -> str:
        self._client.storage.from_(self._bucket).upload(
            path=key,
            file=content,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return f"supabase://{self._bucket}/{key}"
