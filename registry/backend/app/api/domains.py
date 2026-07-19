"""API routes for domain name registrations and registrar transfers."""

import logging
import base64

import jwt
from fastapi import APIRouter, HTTPException, Query, status

from app.models import Domain, DomainAuthInfo, DomainCreate, DomainTransferRequest
from app.store import (
    DomainAlreadyExistsError,
    DomainNotFoundError,
    InvalidTransferTokenError,
    RegistrarNotFoundError,
    SameRegistrarError,
    domain_store,
    registrar_store,
)

TRANSFER_OPERATION = "write:transfer"

logger = logging.getLogger("registry.domains")

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
def transfer_domain(
    name: str,
    payload: DomainTransferRequest,
    transfer_assertion: str = Query(
        ...,
        description=(
            "Base64-encoded JWT, signed by the losing registrar's private "
            "key, asserting {\"operation\": \"write:transfer\", \"domain\": ...}"
        ),
    ),
) -> Domain:
    """Pull-transfer a domain to a new (gaining) registrar.

    Two independent checks must both pass:
    1. `transfer_token` must match the domain's current transfer token.
    2. `transfer_assertion` must be a JWT signed by the *current* sponsoring
       registrar's own public key (as registered in our directory), whose
       claims name this exact operation and domain - proving the losing
       registrar authorized this specific transfer.
    """

    logger.info(
        "Transfer request for domain %s to registrar %s", name, payload.gaining_registrar
    )

    logger.info("Transfer assertion (base64): %s", transfer_assertion)
    
    try:
        domain = domain_store.get(name)
    except DomainNotFoundError:
        raise HTTPException(status_code=404, detail="Domain not found")

    try:
        registrar = registrar_store.get(domain.registrar)
    except RegistrarNotFoundError:
        raise HTTPException(
            status_code=403,
            detail=f"Losing registrar '{domain.registrar}' has no registered public key",
        )

    try:
        assertion_jwt = base64.urlsafe_b64decode(transfer_assertion.encode()).decode()
        logger.info("Transfer assertion (decoded): %s", assertion_jwt)

        claims = jwt.decode(assertion_jwt, registrar.public_key, algorithms=["RS256"])
    except Exception as exc:
        raise HTTPException(status_code=403, detail=f"Invalid transfer assertion: {exc}")

    logger.info(
        "Transfer assertion claims for domain %s: %s", name, claims
    )
    
    if claims.get("operation") != TRANSFER_OPERATION:
        raise HTTPException(
            status_code=403,
            detail=f"Transfer assertion has unexpected operation: {claims.get('operation')!r}",
        )
    if claims.get("domain") != name:
        raise HTTPException(
            status_code=403,
            detail=f"Transfer assertion is for domain {claims.get('domain')!r}, expected {name!r}",
        )

    try:
        return domain_store.transfer(
            name, payload.gaining_registrar, payload.transfer_token, payload.registrant
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
