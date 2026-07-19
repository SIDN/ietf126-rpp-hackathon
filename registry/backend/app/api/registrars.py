"""Registrar directory + cross-registrar transfer-authorization broker.

Each registrar portal self-registers here on startup so the registry knows
where to redirect the browser back to (its `callback_url`) once another
registrar has processed a transfer-authorization request on its behalf.
This lets the "losing" registrar always redirect to one fixed URL on the
registry (`/transfer/callback`) - it never needs to know the "gaining"
registrar's own callback URL itself.
"""


import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.models import Registrar
from app.store import RegistrarNotFoundError, registrar_store

logger = logging.getLogger("registry.registrars")
    
router = APIRouter(tags=["registrars"])


@router.post("/registrars/register", response_model=Registrar)
def register_registrar(payload: Registrar) -> Registrar:
    """Upsert this registrar's directory entry (name -> callback URLs)."""
    return registrar_store.register(payload)


@router.get("/registrars/{name}", response_model=Registrar)
def get_registrar(name: str) -> Registrar:
    try:
        return registrar_store.get(name)
    except RegistrarNotFoundError:
        raise HTTPException(status_code=404, detail=f"Registrar not registered: {name}")


@router.get("/transfer/callback")
def transfer_callback(request: Request) -> RedirectResponse:
    """Fixed callback the losing registrar always redirects to once it has
    processed a transfer-authorization request.

    Looks up the requesting (gaining) registrar's own callback URL from the
    directory and forwards the browser there with the same query params,
    so the losing registrar never needs to know that URL itself.
    """

    logger.info("Received transfer callback from losing registrar, request: %s", request)

    registrar_name = request.query_params.get("registrar")
    if not registrar_name:
        raise HTTPException(status_code=400, detail="Missing 'registrar' query parameter")

    try:
        registrar = registrar_store.get(registrar_name)
    except RegistrarNotFoundError:
        raise HTTPException(status_code=404, detail=f"Unknown registrar: {registrar_name}")

    query_string = request.url.query
    target = f"{registrar.callback_url}?{query_string}" if query_string else registrar.callback_url
    
    logger.info("Redirecting browser to gaining registrar %s callback URL: %s", registrar_name, target)
    
    return RedirectResponse(target)
