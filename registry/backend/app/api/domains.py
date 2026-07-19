"""API routes for domain name registrations and registrar transfers."""

from fastapi import APIRouter, HTTPException, Query, status

from app.models import Domain, DomainAuthInfo, DomainCreate, DomainTransferRequest
from app.store import (
    DomainAlreadyExistsError,
    DomainNotFoundError,
    InvalidTransferTokenError,
    SameRegistrarError,
    domain_store,
)

router = APIRouter(prefix="/domains", tags=["domains"])


@router.get("", response_model=list[Domain])
def list_domains(
    registrar: str | None = Query(
        default=None, description="Filter to domains sponsored by this registrar"
    ),
) -> list[Domain]:
    return domain_store.list(registrar=registrar)


@router.post("", response_model=Domain, status_code=status.HTTP_201_CREATED)
def create_domain(payload: DomainCreate) -> Domain:
    try:
        return domain_store.create(payload)
    except DomainAlreadyExistsError:
        raise HTTPException(status_code=409, detail="Domain already exists")


@router.get("/{name}", response_model=Domain)
def get_domain(name: str) -> Domain:
    try:
        return domain_store.get(name)
    except DomainNotFoundError:
        raise HTTPException(status_code=404, detail="Domain not found")


@router.get("/{name}/auth-info", response_model=DomainAuthInfo)
def get_domain_auth_info(name: str) -> DomainAuthInfo:
    """Return the domain's transfer token.

    Intended to be requested by the domain's current sponsoring registrar so
    it can be shared out-of-band with whoever wants to pull the domain away.
    """
    try:
        return domain_store.get_auth_info(name)
    except DomainNotFoundError:
        raise HTTPException(status_code=404, detail="Domain not found")


@router.post("/{name}/transfer", response_model=Domain)
def transfer_domain(name: str, payload: DomainTransferRequest) -> Domain:
    """Pull-transfer a domain to a new (gaining) registrar.

    The transfer is only applied if `transfer_token` matches the domain's
    current transfer token - this is how the losing registrar's
    authorization for the transfer is verified.
    """
    try:
        return domain_store.transfer(
            name, payload.gaining_registrar, payload.transfer_token
        )
    except DomainNotFoundError:
        raise HTTPException(status_code=404, detail="Domain not found")
    except InvalidTransferTokenError:
        raise HTTPException(status_code=403, detail="Transfer token does not match")
    except SameRegistrarError:
        raise HTTPException(
            status_code=400,
            detail="Domain is already sponsored by that registrar",
        )
