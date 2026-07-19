"""Server-side session store for logged-in registrar users.

Sessions live only in memory (fine for this hackathon's single-process
dev server). The browser holds an opaque, HttpOnly session cookie - it
never sees OAuth2 tokens directly.
"""

import secrets
import time
from dataclasses import dataclass


@dataclass
class Session:
    subject: str
    username: str | None
    email: str | None
    name: str | None
    expires_at: float


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(
        self,
        *,
        subject: str,
        username: str | None,
        email: str | None,
        name: str | None,
        ttl_seconds: int,
    ) -> str:
        session_id = secrets.token_urlsafe(32)
        self._sessions[session_id] = Session(
            subject=subject,
            username=username,
            email=email,
            name=name,
            expires_at=time.time() + ttl_seconds,
        )
        return session_id

    def get(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.expires_at < time.time():
            del self._sessions[session_id]
            return None
        return session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


session_store = SessionStore()
