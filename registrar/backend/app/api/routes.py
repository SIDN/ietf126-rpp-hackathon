"""API routes for the registrar portal."""

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app import registry_client
from app.auth import require_login
from app.core.config import settings
from app.models import Domain, DomainAuthInfo, TransferRequest
from app.sessions import Session

router = APIRouter(tags=["registrar"])


@router.get("/me")
def get_me() -> dict[str, str]:
    return {"registrar_name": settings.registrar_name}


@router.get("/domains", response_model=list[Domain])
async def list_my_domains() -> list[Domain]:
    try:
        domains = await registry_client.list_domains(registrar=settings.registrar_name)
    except registry_client.RegistryClientError as exc:
        raise HTTPException(status_code=502, detail=exc.detail)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Registry unreachable: {exc}")
    return domains


@router.get("/domains/{name}/transfer-token", response_model=DomainAuthInfo)
async def get_domain_transfer_token(name: str) -> DomainAuthInfo:
    """Reveal a domain's transfer token, so it can be shared out-of-band
    with whoever wants to pull the domain away to another registrar.

    Only available for domains currently sponsored by this registrar - the
    losing registrar is the one that controls (and hands out) the token.
    """
    try:
        domain = await registry_client.get_domain(name)
    except registry_client.RegistryClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Registry unreachable: {exc}")

    if domain["registrar"] != settings.registrar_name:
        raise HTTPException(
            status_code=403,
            detail="This registrar does not sponsor that domain",
        )

    try:
        return await registry_client.get_auth_info(name)
    except registry_client.RegistryClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Registry unreachable: {exc}")


@router.post("/transfers", response_model=Domain)
async def start_transfer(
    payload: TransferRequest,
    session: Session = Depends(require_login),
) -> Domain:
    """Pull `payload.domain_name` to this registrar using the transfer
    token supplied by the domain's current (losing) registrar.

    Requires an active login session - the caller must have signed in via
    the OIDC provider before a transfer is allowed.
    """
    try:
        domain = await registry_client.transfer_domain(
            payload.domain_name, settings.registrar_name, payload.transfer_token
        )
    except registry_client.RegistryClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Registry unreachable: {exc}")
    return domain
