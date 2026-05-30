from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    secret_key: str = "change-me"
    # Comma-separated allowed CORS origins; "*" allows any (fine for local dev).
    cors_origins: str = "*"
    # When True, tenant-scoped endpoints require a verified Clerk session JWT and
    # derive the tenant from its claims. When False (local dev), everything runs
    # as the single "default" tenant and no token is required.
    enable_auth: bool = False
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    database_url: str = "postgresql://postgres:postgres@localhost:5432/postgres"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "invoice-files"
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    azure_openai_api_version: str = "2024-02-01"
    azure_doc_intel_endpoint: str = ""
    azure_doc_intel_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
