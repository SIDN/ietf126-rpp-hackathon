"""Registrar directory.

Each registrar portal self-registers here on startup so other registrars
can look up its `authorize_url` (where to send a domain owner to
authorize a cross-registrar transfer). The registry is only a directory
lookup here - it is no longer involved in relaying the transfer result
back to the gaining registrar; the losing registrar redirects the browser
directly to the `return_url` the gaining registrar supplied upfront.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.models import Registrar
from app.store import RegistrarNotFoundError, registrar_store

logger = logging.getLogger("registry.registrars")

router = APIRouter(tags=["registrars"])


@router.post("/registrars/register", response_model=Registrar)
def register_registrar(payload: Registrar) -> Registrar:
    """Upsert this registrar's directory entry (name -> authorize_url)."""
    logger.info("Registering registrar directory entry for %s", payload.name)
    
    return registrar_store.register(payload)


@router.get("/registrars/{name}", response_model=Registrar)
def get_registrar(name: str) -> Registrar:

    logger.info("Looking up registrar directory entry for %s", name)

    try:
        return registrar_store.get(name)
    except RegistrarNotFoundError:
        raise HTTPException(status_code=404, detail=f"Registrar not registered: {name}")
