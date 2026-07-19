"""Cross-registrar domain transfer authorization flow.

Modeled as a browser-redirect chain, similar in spirit to OAuth2 Rich
Authorization Requests (RFC 9396):

1. The gaining registrar (this backend, when a signed-in user starts a
   transfer) redirects the browser to the *losing* registrar's own
   authorization endpoint, with:
   - `authorization_details`: a base64url-encoded JSON object describing
     what's being requested (here, just `{"domain": "..."}`).
   - `return_url`: the exact URL (this registrar's own `/transfer/complete`,
     with a correlation `state` baked in) the losing registrar must
     redirect back to once it's done. The registry is no longer involved
     in this handoff - the gaining registrar tells the losing registrar
     directly where to send the result.
2. The losing registrar (this same backend, acting on behalf of the
   domain's current sponsor) requires the domain owner to be logged in,
   then shows them a consent screen (on its own frontend) naming the
   domain and the requesting registrar. The domain owner must explicitly
   approve or cancel - see `/authorize` and `/decision` below.
3. Once a decision is made, this registrar redirects the browser straight
   to the `return_url` it was given. If approved, it appends a *signed*
   JSON assertion (`transfer_assertion`, an RS256 JWT signed with this
   registrar's own private key, containing
   `{"operation": "write:transfer", "domain": "..."}`) plus the domain's
   transfer token, proving the losing registrar authorized this specific
   operation for this specific domain. Each registrar publishes its
   public key to the registry directory on startup.
4. The gaining registrar (this backend again) receives the result at its
   own fixed `/transfer/complete` endpoint and forwards the assertion
   on to the registry (base64-encoded) along with the actual pull
   transfer request. The registry - not the gaining registrar - verifies
   the assertion's signature (against the losing registrar's published
   public key) and claims before applying the transfer.
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

from app import registry_client, signing
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


def _current_registrant(request: Request) -> str | None:
    """The logged-in user's username, which becomes a domain's registrant
    when they complete a transfer. Falls back to email/subject if the
    OIDC provider didn't supply a username."""
    session_id = request.cookies.get(settings.session_cookie_name)
    session = session_store.get(session_id) if session_id else None
    if session is None:
        return None
    return session.username or session.email or session.subject


def _redirect_to_login(request: Request) -> RedirectResponse:
    """Send an unauthenticated browser through the OAuth2 login flow, then
    back to the same URL (path + query) it was trying to reach."""
    next_path = request.url.path
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"
    login_url = f"{settings.api_prefix}/auth/login?{urlencode({'next': next_path})}"
    logger.info("Redirecting to login URL: %s", login_url)
    return RedirectResponse(login_url)


def _append_query(url: str, params: dict) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode(params)}"


def _frontend_redirect(*, success: str | None = None, error: str | None = None) -> str:
    params: dict[str, str] = {}
    if success:
        params["transfer_success"] = success
    if error:
        params["transfer_error"] = error
    return f"{settings.frontend_url}?{urlencode(params)}"


@router.get("/start")
async def start_transfer(request: Request, domain: str = Query(..., min_length=1)) -> RedirectResponse:
    """Gaining side: kick off a pull transfer for `domain` by sending the
    browser to the domain's current (losing) registrar's authorization
    endpoint, telling it exactly where (`return_url`) to send the result."""
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

    return_url = _append_query(settings.transfer_complete_url, {"state": state})

    params = {
        "registrar": settings.registrar_name,
        "authorization_details": authorization_details,
        "return_url": return_url,
    }
    authorize_url = f"{registrar_entry['authorize_url']}?{urlencode(params)}"
    logger.info("Starting transfer of %s: redirecting to %s", domain, authorize_url)
    return RedirectResponse(authorize_url)


@router.get("/authorize")
async def authorize_transfer(
    request: Request,
    registrar: str = Query(..., description="Name of the requesting (gaining) registrar"),
    authorization_details: str = Query(...),
    return_url: str = Query(..., description="Where to redirect once a decision is made"),
) -> RedirectResponse:
    """Losing side: the domain's current sponsor must be logged in here.
    Rather than approving automatically, we send the browser to this
    registrar's own frontend to show a consent screen - the actual
    approve/cancel decision is made there and submitted to `/decision`."""
    if not _is_logged_in(request):
        logger.info("User not logged in, redirecting to login before showing transfer consent")
        return _redirect_to_login(request)

    try:
        details = json.loads(base64.urlsafe_b64decode(authorization_details.encode()))
        domain = details["domain"]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid authorization_details: {exc}")

    params = {
        "transfer_consent": "1",
        "domain": domain,
        "registrar": registrar,
        "return_url": return_url,
    }
    logger.info(
        "Prompting for transfer consent: domain=%s requesting registrar=%s return_url=%s",
        domain,
        registrar,
        return_url,
    )
    return RedirectResponse(f"{settings.frontend_url}?{urlencode(params)}")


@router.get("/decision")
async def transfer_decision(
    request: Request,
    domain: str = Query(...),
    registrar: str = Query(..., description="Name of the requesting (gaining) registrar"),
    return_url: str = Query(...),
    approved: bool = Query(...),
) -> RedirectResponse:
    """Losing side: the domain owner's approve/cancel decision from the
    consent screen. Redirects directly to `return_url` (supplied by the
    gaining registrar up front) - the registry is never involved here."""
    if not _is_logged_in(request):
        return _redirect_to_login(request)

    if not approved:
        logger.info("Transfer of %s to %s was cancelled by the domain owner", domain, registrar)
        return RedirectResponse(
            _append_query(
                return_url,
                {"approved": "false", "error": "Transfer was cancelled by the domain owner"},
            )
        )

    try:
        domain_info = await registry_client.get_domain(domain)
        if domain_info["registrar"] != settings.registrar_name:
            return RedirectResponse(
                _append_query(
                    return_url,
                    {"approved": "false", "error": "This registrar does not sponsor that domain"},
                )
            )
        auth_info = await registry_client.get_auth_info(domain)
    except registry_client.RegistryClientError as exc:
        return RedirectResponse(_append_query(return_url, {"approved": "false", "error": exc.detail}))
    except httpx.RequestError as exc:
        return RedirectResponse(
            _append_query(return_url, {"approved": "false", "error": f"Registry unreachable: {exc}"})
        )

    assertion = signing.sign_transfer_assertion(domain, issuer=settings.registrar_name)
    redirect_url = _append_query(
        return_url,
        {"transfer_assertion": assertion, "transfer_token": auth_info["transfer_token"]},
    )
    logger.info(
        "Approved transfer of %s to %s, redirecting to return_url with signed assertion",
        domain,
        registrar,
    )
    return RedirectResponse(redirect_url)


@router.get("/complete")
async def complete_transfer(
    request: Request,
    state: str = Query(...),
    transfer_assertion: str | None = Query(default=None),
    transfer_token: str | None = Query(default=None),
    approved: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    """Gaining side: receives the result directly from the losing
    registrar and forwards it to the registry, which verifies the signed
    assertion (against the losing registrar's published public key) and
    completes the actual pull transfer."""
    pending = _consume_transfer(state)
    if pending is None:
        return RedirectResponse(_frontend_redirect(error="Invalid or expired transfer request"))

    domain = pending["domain"]

    if approved == "false" or not transfer_assertion or not transfer_token:
        message = error or "Transfer was not authorized by the losing registrar"
        return RedirectResponse(_frontend_redirect(error=message))

    registrant = _current_registrant(request)
    if not registrant:
        return RedirectResponse(_frontend_redirect(error="Login required to complete a transfer"))

    transfer_assertion_b64 = base64.urlsafe_b64encode(transfer_assertion.encode()).decode()

    try:
        await registry_client.transfer_domain(
            domain, settings.registrar_name, transfer_token, transfer_assertion_b64, registrant
        )
    except registry_client.RegistryClientError as exc:
        return RedirectResponse(_frontend_redirect(error=exc.detail))
    except httpx.RequestError as exc:
        return RedirectResponse(_frontend_redirect(error=f"Registry unreachable: {exc}"))

    return RedirectResponse(_frontend_redirect(success=domain))

