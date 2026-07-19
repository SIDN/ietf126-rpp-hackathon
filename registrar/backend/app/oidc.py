"""OIDC discovery, authorization code exchange, and ID token verification
for the registrar portal's confidential OAuth2 client.
"""

import logging
import time

import jwt
from jwt import PyJWKClient

from app.core.config import settings
from app.http_client import new_client

logger = logging.getLogger("registrar.oidc")

_DISCOVERY_TTL_SECONDS = 300

_discovery_cache: dict | None = None
_discovery_cached_at: float = 0.0
_jwks_client: PyJWKClient | None = None


class OAuth2Error(Exception):
    """Raised when the OIDC provider rejects a discovery, token, or
    verification step."""


async def get_discovery_document() -> dict:
    global _discovery_cache, _discovery_cached_at
    now = time.monotonic()
    if _discovery_cache is None or (now - _discovery_cached_at) >= _DISCOVERY_TTL_SECONDS:
        url = f"{settings.oauth2_issuer.rstrip('/')}/.well-known/openid-configuration"
        logger.info("Fetching OIDC discovery document from %s", url)
        async with new_client() as client:
            response = await client.get(url)
        if response.is_error:
            raise OAuth2Error(
                f"OIDC discovery failed ({response.status_code}): {response.text}"
            )
        _discovery_cache = response.json()
        _discovery_cached_at = now
        logger.info(
            "OIDC discovery ok - authorization_endpoint=%s token_endpoint=%s jwks_uri=%s",
            _discovery_cache.get("authorization_endpoint"),
            _discovery_cache.get("token_endpoint"),
            _discovery_cache.get("jwks_uri"),
        )
    return _discovery_cache


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange an authorization code for tokens using this confidential
    client's client_id + client_secret (Authorization Code flow)."""

    logger.info("getting token, using settings.oauth2_redirect_uri=%s", settings.oauth2_redirect_uri )

    discovery = await get_discovery_document()
    async with new_client() as client:
        response = await client.post(
            discovery["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.oauth2_redirect_uri,
                "client_id": settings.oauth2_client_id,
                "client_secret": settings.oauth2_client_secret,
            },
        )
    if response.is_error:
        raise OAuth2Error(
            f"Token exchange failed ({response.status_code}): {response.text}"
        )
    return response.json()


def _get_jwks_client(jwks_uri: str) -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        logger.info("Fetching signing keys from %s", jwks_uri)
        _jwks_client = PyJWKClient(jwks_uri)
    return _jwks_client


async def verify_id_token(id_token: str) -> dict:
    """Verify the ID token's signature, issuer, and audience, returning its
    claims. Raises OAuth2Error if verification fails."""
    discovery = await get_discovery_document()
    jwks_client = _get_jwks_client(discovery["jwks_uri"])
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        return jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=discovery["issuer"],
            audience=settings.oauth2_client_id,
        )
    except jwt.PyJWTError as exc:
        raise OAuth2Error(f"Invalid ID token: {exc}") from exc
