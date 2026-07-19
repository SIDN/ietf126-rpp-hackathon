"""HTTP client for talking to the registry service."""

import logging

import httpx

from app.core.config import settings
from app.http_client import new_client

logger = logging.getLogger("registrar.registry_client")

class RegistryClientError(Exception):
    """Raised when the registry rejects or fails a request."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _raise_for_error(response: httpx.Response) -> None:
    if not response.is_error:
        return
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text
    raise RegistryClientError(response.status_code, detail)


async def list_domains(registrar: str | None = None) -> list[dict]:
    params = {"registrar": registrar} if registrar else None
    async with new_client(base_url=settings.registry_api_url) as client:
        response = await client.get("/domains", params=params)
    _raise_for_error(response)
    return response.json()


async def get_domain(domain_name: str) -> dict:
    async with new_client(base_url=settings.registry_api_url) as client:
        response = await client.get(f"/domains/{domain_name}")
    _raise_for_error(response)
    return response.json()


async def get_auth_info(domain_name: str) -> dict:
    async with new_client(base_url=settings.registry_api_url) as client:
        response = await client.get(f"/domains/{domain_name}/auth-info")
    _raise_for_error(response)
    return response.json()


async def transfer_domain(
    domain_name: str, gaining_registrar: str, transfer_token: str
) -> dict:
    async with new_client(base_url=settings.registry_api_url) as client:
        response = await client.post(
            f"/domains/{domain_name}/transfer",
            json={
                "gaining_registrar": gaining_registrar,
                "transfer_token": transfer_token,
            },
        )
    _raise_for_error(response)
    return response.json()


async def get_registrar(registrar_name: str) -> dict:
    """Look up another registrar's directory entry (its authorize/callback
    URLs) so we can redirect to it to start a cross-registrar transfer."""
    async with new_client(base_url=settings.registry_api_url) as client:
        response = await client.get(f"/registrars/{registrar_name}")
    _raise_for_error(response)

    logger.info("Retrieved registrar directory entry for %s: %s", registrar_name, response.json())

    return response.json()


async def register_registrar(name: str, authorize_url: str, callback_url: str) -> dict:
    """Self-register this registrar's directory entry with the registry."""
    async with new_client(base_url=settings.registry_api_url) as client:
        response = await client.post(
            "/registrars/register",
            json={"name": name, "authorize_url": authorize_url, "callback_url": callback_url},
        )
    _raise_for_error(response)
    return response.json()
