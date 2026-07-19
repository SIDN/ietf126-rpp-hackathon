"""OAuth2 login endpoints for the registrar portal.

The registrar backend acts as a confidential OAuth2 client: it owns the
client secret and performs the Authorization Code exchange itself. The
browser is only ever given an HttpOnly session cookie - it never sees the
OAuth2 access/ID tokens.

Flow:
1. Browser navigates (full page load, not fetch) to GET /auth/login.
2. We redirect it to the provider's authorization endpoint.
3. The provider redirects back to GET /auth/callback with a code.
4. We exchange the code for tokens using client_id + client_secret,
   verify the ID token, and start a server-side session.
5. We set an HttpOnly session cookie and redirect back to the frontend.
"""

import logging
import secrets
import time
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, HTTPException, Query, Response
from fastapi.responses import RedirectResponse

from app import oidc
from app.core.config import settings
from app.sessions import session_store

logger = logging.getLogger("registrar.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory CSRF state store: state -> {created_at, next}. Cleared once
# consumed; fine for a single dev-server process.
_PENDING_STATE_TTL_SECONDS = 600
_pending_states: dict[str, dict] = {}


def _safe_next(next_path: str | None) -> str | None:
    """Only allow same-origin relative paths for `next`, to avoid turning
    it into an open redirect."""
    if not next_path:
        return None
    if not next_path.startswith("/") or next_path.startswith("//"):
        return None
    if "://" in next_path:
        return None
    return next_path


def _remember_state(state: str, next_path: str | None = None) -> None:
    now = time.monotonic()
    # Opportunistically drop stale entries so this doesn't grow unbounded.
    for pending, info in list(_pending_states.items()):
        if now - info["created_at"] > _PENDING_STATE_TTL_SECONDS:
            _pending_states.pop(pending, None)
    _pending_states[state] = {"created_at": now, "next": next_path}


def _consume_state(state: str) -> dict | None:
    return _pending_states.pop(state, None)


@router.get("/login")
async def login(next: str | None = Query(default=None)) -> RedirectResponse:
    logger.info("Login requested, next=%s", next)

    try:
        discovery = await oidc.get_discovery_document()
    except oidc.OAuth2Error as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    state = secrets.token_urlsafe(24)
    _remember_state(state, next_path=_safe_next(next))

    logger.info("remembering next=%s for state=%s", next, state)
    
    params = {
        "response_type": "code",
        "client_id": settings.oauth2_client_id,
        "redirect_uri": settings.oauth2_redirect_uri,
        "scope": "openid profile email",
        "state": state,
    }

    logger.info("Params for authorization request: %s", params)

    authorize_url = f"{discovery['authorization_endpoint']}?{urlencode(params)}"
    logger.info("Redirecting browser to authorize URL: %s", authorize_url)
    return RedirectResponse(authorize_url)


@router.get("/callback")
async def callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    
    logger.info("OAuth2 callback received: code=%s, state=%s, error=%s", code, state, error)

    if error:
        logger.warning("OAuth2 callback returned an error: %s", error_description or error)
        raise HTTPException(
            status_code=401, detail=f"Login failed: {error_description or error}"
        )
    pending = _consume_state(state) if state else None

    logger.info("Consumed pending state: %s", pending)

    # if not code or pending is None:
    #     logger.warning("OAuth2 callback had a missing/invalid/expired state")
    #     raise HTTPException(status_code=400, detail="Invalid or expired OAuth2 callback")

    try:
        tokens = await oidc.exchange_code_for_tokens(code)
        claims = await oidc.verify_id_token(tokens["id_token"])
    except oidc.OAuth2Error as exc:
        logger.warning("OAuth2 login failed: %s", exc)
        raise HTTPException(status_code=401, detail=str(exc))

    logger.info("Login succeeded for subject=%s", claims.get("sub"))
    session_id = session_store.create(
        subject=str(claims.get("sub", "")),
        username=claims.get("preferred_username") or claims.get("nickname"),
        email=claims.get("email"),
        name=claims.get("name"),
        ttl_seconds=settings.session_ttl_seconds,
    )

    logger.info("Created session %s for subject=%s", session_id, claims.get("sub"))

    next = pending["next"] if pending and "next" in pending else None
    logger.info("Redirecting browser to next=%s after login", next or settings.frontend_url)

    # `next` (if present) is a same-origin path on this backend, e.g. to
    # resume a cross-registrar transfer-authorization request that
    # required login. Otherwise, send the browser back to the frontend.
    response = RedirectResponse(next or settings.frontend_url)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=False,  # local dev over http; set True behind TLS in prod
        max_age=settings.session_ttl_seconds,
    )

    logger.info("Responding to browser with session cookie and redirect to %s", response.headers.get("location"))

    return response


@router.get("/session")
async def get_session(
    session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> dict:
    session = session_store.get(session_id) if session_id else None
    if session is None:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "email": session.email,
        "username": session.username,
        "name": session.name,
    }


@router.post("/logout")
async def logout(
    response: Response,
    session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> dict:
    if session_id:
        session_store.delete(session_id)
    response.delete_cookie(settings.session_cookie_name)
    return {"ok": True}
