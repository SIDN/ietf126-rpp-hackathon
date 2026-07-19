"""Cross-registrar domain transfer authorization flow.

Modeled as a browser-redirect chain, similar in spirit to OAuth2 Rich
Authorization Requests (RFC 9396):

1. The gaining registrar (this backend, when a signed-in user starts a
   transfer) redirects the browser to the *losing* registrar's own
   authorization endpoint, with an `authorization_details` query
   parameter: a base64url-encoded JSON object describing what's being
   requested (here, just `{"domain": "..."}`).
2. The losing registrar (this same backend, acting on behalf of the
   domain's current sponsor) requires the domain owner to be logged in,
   then shows them a consent screen (on its own frontend) naming the
   domain and the requesting registrar. The domain owner must explicitly
   approve or cancel - see `/authorize` and `/decision` below.
3. Once a decision is made, this registrar *always* redirects the browser
   to one fixed URL on the registry (`/transfer/callback`) - it never
   needs to know the gaining registrar's own callback URL.
4. The registry looks up the gaining registrar's callback URL from its
   directory (registrars self-register it on startup) and redirects the
   browser there.
5. The gaining registrar (this backend again) receives the result at its
   own fixed `/transfer/complete` endpoint and, if authorized, completes
   the actual pull transfer against the registry.
"""

import base64
import json
import logging
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app import registry_client
from app.core.config import settings
from app.sessions import session_store

logger = logging.getLogger("registrar.transfer")

router = APIRouter(prefix="/transfer", tags=["transfer"])

# In-memory correlation store for transfers this registrar initiated as the
# gaining side: state -> {domain, created_at}. Fine for a single dev-server
# process.
_PENDING_TTL_SECONDS = 600
_pending_transfers: dict[str, dict] = {}


def _remember_transfer(state: str, domain: str) -> None:
    now = time.monotonic()
    for pending, info in list(_pending_transfers.items()):
        if now - info["created_at"] > _PENDING_TTL_SECONDS:
            _pending_transfers.pop(pending, None)
    _pending_transfers[state] = {"domain": domain, "created_at": now}


def _consume_transfer(state: str) -> dict | None:
    return _pending_transfers.pop(state, None)


def _is_logged_in(request: Request) -> bool:
    session_id = request.cookies.get(settings.session_cookie_name)
    return bool(session_id and session_store.get(session_id) is not None)


def _redirect_to_login(request: Request) -> RedirectResponse:
    """Send an unauthenticated browser through the OAuth2 login flow, then
    back to the same URL (path + query) it was trying to reach."""
    next_path = request.url.path

    logger.info("Remembering next=%s for login redirect", next_path)

    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"
    login_url = f"{settings.api_prefix}/auth/login?{urlencode({'next': next_path})}"
    
    logger.info("Redirecting to login URL: %s", login_url)
    
    return RedirectResponse(login_url)


@router.get("/start")
async def start_transfer(request: Request, domain: str = Query(..., min_length=1)) -> RedirectResponse:
    """Gaining side: kick off a pull transfer for `domain` by sending the
    browser to the domain's current (losing) registrar's authorization
    endpoint."""
    if not _is_logged_in(request):
        logger.info("User not logged in, redirecting to login before starting transfer")
        return _redirect_to_login(request)

    try:
        domain_info = await registry_client.get_domain(domain)
    except registry_client.RegistryClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Registry unreachable: {exc}")

    losing_registrar = domain_info["registrar"]
    if losing_registrar == settings.registrar_name:
        raise HTTPException(
            status_code=400, detail="Domain is already sponsored by this registrar"
        )

    try:
        registrar_entry = await registry_client.get_registrar(losing_registrar)
    except registry_client.RegistryClientError:
        raise HTTPException(
            status_code=502,
            detail=f"Losing registrar '{losing_registrar}' is not registered with the registry",
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Registry unreachable: {exc}")

    state = secrets.token_urlsafe(24)
    _remember_transfer(state, domain)

    authorization_details = base64.urlsafe_b64encode(
        json.dumps({"domain": domain}).encode()
    ).decode()

    params = {
        "registrar": settings.registrar_name,
        "authorization_details": authorization_details,
        "state": state,
    }
    authorize_url = f"{registrar_entry['authorize_url']}?{urlencode(params)}"
    logger.info("Starting transfer of %s: redirecting to %s", domain, authorize_url)
    return RedirectResponse(authorize_url)


@router.get("/authorize")
async def authorize_transfer(
    request: Request,
    registrar: str = Query(..., description="Name of the requesting (gaining) registrar"),
    authorization_details: str = Query(...),
    state: str = Query(...),
) -> RedirectResponse:
    """Losing side: the domain's current sponsor must be logged in here.
    Rather than approving automatically, we send the browser to this
    registrar's own frontend to show a consent screen - the actual
    approve/cancel decision is made there and submitted to `/decision`."""
    if not _is_logged_in(request):
        logger.info("User not logged in, redirecting to login before showing transfer consent")
        return _redirect_to_login(request)
    
    logger.info("Received transfer authorization request: registrar=%s, state=%s, authorization_details=%s", registrar, state, authorization_details)

    try:
        details = json.loads(base64.urlsafe_b64decode(authorization_details.encode()))
        domain = details["domain"]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid authorization_details: {exc}")

    params = {
        "transfer_consent": "1",
        "domain": domain,
        "registrar": registrar,
        "state": state,
    }
    logger.info(
        "Prompting for transfer consent: domain=%s requesting registrar=%s",
        domain,
        registrar,
    )
    return RedirectResponse(f"{settings.frontend_url}?{urlencode(params)}")


@router.get("/decision")
async def transfer_decision(
    request: Request,
    domain: str = Query(...),
    registrar: str = Query(..., description="Name of the requesting (gaining) registrar"),
    state: str = Query(...),
    approved: bool = Query(...),
) -> RedirectResponse:
    """Losing side: the domain owner's approve/cancel decision from the
    consent screen. Always redirects to the registry's fixed transfer
    callback - never directly to the gaining registrar."""
    if not _is_logged_in(request):
        return _redirect_to_login(request)

    result: dict[str, str] = {"registrar": registrar, "state": state, "domain": domain}
    if not approved:
        result["approved"] = "false"
        result["error"] = "Transfer was cancelled by the domain owner"
    else:
        try:
            domain_info = await registry_client.get_domain(domain)
            if domain_info["registrar"] != settings.registrar_name:
                result["approved"] = "false"
                result["error"] = "This registrar does not sponsor that domain"
            else:
                auth_info = await registry_client.get_auth_info(domain)
                result["approved"] = "true"
                result["transfer_token"] = auth_info["transfer_token"]
        except registry_client.RegistryClientError as exc:
            result["approved"] = "false"
            result["error"] = exc.detail
        except httpx.RequestError as exc:
            result["approved"] = "false"
            result["error"] = f"Registry unreachable: {exc}"

    callback_url = f"{settings.registry_transfer_callback_url}?{urlencode(result)}"
    logger.info(
        "Transfer decision for %s (registrar=%s): approved=%s, redirecting to registry callback",
        domain,
        registrar,
        result.get("approved"),
    )
    return RedirectResponse(callback_url)


@router.get("/complete")
async def complete_transfer(
    state: str = Query(...),
    domain: str = Query(...),
    approved: str = Query(...),
    transfer_token: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    """Gaining side: receives the brokered result from the registry and,
    if authorized, completes the actual pull transfer."""
    pending = _consume_transfer(state)
    if pending is None or pending["domain"] != domain:
        return RedirectResponse(
            f"{settings.frontend_url}?{urlencode({'transfer_error': 'Invalid or expired transfer request'})}"
        )

    if approved != "true" or not transfer_token:
        message = error or "Transfer was not authorized by the losing registrar"
        return RedirectResponse(f"{settings.frontend_url}?{urlencode({'transfer_error': message})}")

    try:
        await registry_client.transfer_domain(domain, settings.registrar_name, transfer_token)
    except registry_client.RegistryClientError as exc:
        return RedirectResponse(
            f"{settings.frontend_url}?{urlencode({'transfer_error': exc.detail})}"
        )
    except httpx.RequestError as exc:
        return RedirectResponse(
            f"{settings.frontend_url}?{urlencode({'transfer_error': f'Registry unreachable: {exc}'})}"
        )

    return RedirectResponse(f"{settings.frontend_url}?{urlencode({'transfer_success': domain})}")
