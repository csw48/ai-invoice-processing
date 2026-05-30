"""Server-side authentication: derive the tenant id from a verified Clerk JWT.

The X-Client-Id header is NOT trusted as a tenant key — it is spoofable. When
auth is enabled we verify the Clerk session token (RS256, against Clerk's JWKS)
and take the tenant from its `org_id`/`sub` claim. When auth is disabled (local
dev) every request runs as the single "default" tenant.
"""
from functools import lru_cache

from fastapi import Header, HTTPException

from app.core.config import get_settings
from app.repositories import ConfigRepository


@lru_cache
def _jwks_client():
    from jwt import PyJWKClient

    settings = get_settings()
    if not settings.clerk_jwks_url:
        raise RuntimeError("CLERK_JWKS_URL is not configured but auth is enabled")
    return PyJWKClient(settings.clerk_jwks_url)


def _verify_clerk_token(token: str) -> dict:
    import jwt

    settings = get_settings()
    signing_key = _jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=settings.clerk_issuer or None,
        options={
            "verify_aud": False,
            "verify_iss": bool(settings.clerk_issuer),
        },
    )


def get_client_id(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: the verified tenant id for this request.

    Raises 401 when auth is enabled and the bearer token is missing or invalid.
    """
    settings = get_settings()
    if not settings.enable_auth:
        return ConfigRepository.DEFAULT_ID

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = _verify_clerk_token(token)
    except Exception as exc:  # invalid signature, expired, malformed, JWKS failure
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    client_id = claims.get("org_id") or claims.get("sub")
    if not client_id:
        raise HTTPException(status_code=401, detail="Token has no tenant claim")
    return client_id
