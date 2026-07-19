"""In-memory data store for registry entries and domains.

This is intentionally simple (no database) so the hackathon project can run
without any external services. Swap this out for a real persistence layer
later if needed.
"""

import secrets
from datetime import datetime
from threading import Lock
from uuid import UUID

from pydantic import BaseModel

from app.models import (
    Domain,
    DomainAuthInfo,
    DomainCreate,
    Entry,
    EntryCreate,
    EntryUpdate,
    Registrar,
)


class EntryNotFoundError(Exception):
    pass


class DomainNotFoundError(Exception):
    pass


class DomainAlreadyExistsError(Exception):
    pass


class InvalidTransferTokenError(Exception):
    """Raised when a pull transfer request has a non-matching token."""

    pass


class SameRegistrarError(Exception):
    """Raised when a transfer targets the domain's current registrar."""

    pass


class EntryStore:
    def __init__(self) -> None:
        self._entries: dict[UUID, Entry] = {}
        self._lock = Lock()

    def list(self) -> list[Entry]:
        with self._lock:
            return list(self._entries.values())

    def get(self, entry_id: UUID) -> Entry:
        with self._lock:
            entry = self._entries.get(entry_id)
        if entry is None:
            raise EntryNotFoundError(entry_id)
        return entry

    def create(self, payload: EntryCreate) -> Entry:
        entry = Entry(**payload.model_dump())
        with self._lock:
            self._entries[entry.id] = entry
        return entry

    def update(self, entry_id: UUID, payload: EntryUpdate) -> Entry:
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is None:
                raise EntryNotFoundError(entry_id)
            updated = entry.model_copy(
                update={
                    **payload.model_dump(exclude_unset=True),
                    "updated_at": datetime.utcnow(),
                }
            )
            self._entries[entry_id] = updated
        return updated

    def delete(self, entry_id: UUID) -> None:
        with self._lock:
            if entry_id not in self._entries:
                raise EntryNotFoundError(entry_id)
            del self._entries[entry_id]


store = EntryStore()


def _generate_transfer_token() -> str:
    """Generate a cryptographically secure, unguessable transfer token."""
    return secrets.token_urlsafe(24)


class _DomainRecord(BaseModel):
    """Internal, full representation of a domain including its secret
    transfer token. Never returned directly from the API - always convert
    via `to_public()` or `to_auth_info()` first.
    """

    name: str
    registrar: str
    transfer_token: str
    created_at: datetime
    updated_at: datetime

    def to_public(self) -> Domain:
        return Domain(
            name=self.name,
            registrar=self.registrar,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def to_auth_info(self) -> DomainAuthInfo:
        return DomainAuthInfo(name=self.name, transfer_token=self.transfer_token)


class DomainStore:
    """Tracks which registrar currently sponsors each domain name.

    Transfers use a pull model: the gaining registrar submits the domain's
    transfer token (an attribute of the domain, only known to its current
    sponsoring registrar). The transfer is only applied if the supplied
    token matches - this is how the losing registrar's authorization is
    verified.
    """

    def __init__(self) -> None:
        self._domains: dict[str, _DomainRecord] = {}
        self._lock = Lock()

    @staticmethod
    def _key(name: str) -> str:
        return name.strip().lower()

    def _get_record(self, name: str) -> _DomainRecord:
        with self._lock:
            record = self._domains.get(self._key(name))
        if record is None:
            raise DomainNotFoundError(name)
        return record

    def list(self, registrar: str | None = None) -> list[Domain]:
        with self._lock:
            records = list(self._domains.values())
        if registrar is not None:
            records = [r for r in records if r.registrar == registrar]
        return [r.to_public() for r in records]

    def get(self, name: str) -> Domain:
        return self._get_record(name).to_public()

    def get_auth_info(self, name: str) -> DomainAuthInfo:
        return self._get_record(name).to_auth_info()

    def create(self, payload: DomainCreate) -> Domain:
        key = self._key(payload.name)
        with self._lock:
            if key in self._domains:
                raise DomainAlreadyExistsError(payload.name)
            now = datetime.utcnow()
            record = _DomainRecord(
                name=payload.name,
                registrar=payload.registrar,
                transfer_token=_generate_transfer_token(),
                created_at=now,
                updated_at=now,
            )
            self._domains[key] = record
        return record.to_public()

    def transfer(self, name: str, gaining_registrar: str, transfer_token: str) -> Domain:
        key = self._key(name)
        with self._lock:
            record = self._domains.get(key)
            if record is None:
                raise DomainNotFoundError(name)
            if not secrets.compare_digest(record.transfer_token, transfer_token):
                raise InvalidTransferTokenError(name)
            if record.registrar == gaining_registrar:
                raise SameRegistrarError(name)
            updated = record.model_copy(
                update={
                    "registrar": gaining_registrar,
                    # Rotate the token so the old one can't be reused for
                    # another transfer once this one has completed.
                    "transfer_token": _generate_transfer_token(),
                    "updated_at": datetime.utcnow(),
                }
            )
            self._domains[key] = updated
        return updated.to_public()


domain_store = DomainStore()


class RegistrarNotFoundError(Exception):
    pass


class RegistrarStore:
    """Directory of registrar portal instances, keyed by name.

    Registrars self-register (`POST /registrars/register`) on startup so
    the registry knows where to redirect the browser back to once a
    cross-registrar transfer-authorization request has been processed by
    the losing registrar.
    """

    def __init__(self) -> None:
        self._registrars: dict[str, Registrar] = {}
        self._lock = Lock()

    def register(self, payload: Registrar) -> Registrar:
        with self._lock:
            self._registrars[payload.name] = payload
        return payload

    def get(self, name: str) -> Registrar:
        with self._lock:
            registrar = self._registrars.get(name)
        if registrar is None:
            raise RegistrarNotFoundError(name)
        return registrar

    def list(self) -> list[Registrar]:
        with self._lock:
            return list(self._registrars.values())


registrar_store = RegistrarStore()
