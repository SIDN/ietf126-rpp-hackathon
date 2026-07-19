"""Session-based login requirement for protected registrar endpoints.

The registrar backend is a confidential OAuth2 client: it owns the client
secret and performs the authorization code exchange itself (see oidc.py and
api/auth_routes.py), then keeps a short-lived server-side session. The
browser only ever holds an HttpOnly session cookie - it never sees the
OAuth2 access/ID tokens.
"""

from fastapi import Cookie, HTTPException, status

from app.core.config import settings
from app.sessions import Session, session_store


async def require_login(
    session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> Session:
    """FastAPI dependency that requires an active, logged-in session.

    Raises 401 if there is no session cookie, or it doesn't match a valid,
    unexpired session.
    """
    if session_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required to start a transfer",
        )

    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid - please sign in again",
        )

    return session
