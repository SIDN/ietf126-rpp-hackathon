"""Pydantic models (schemas) for the registry API."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EntryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list)


class EntryCreate(EntryBase):
    pass


class EntryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None


class Entry(EntryBase):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DomainBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=253)
    registrar: str = Field(..., min_length=1, max_length=200)


class DomainCreate(DomainBase):
    pass


class Domain(DomainBase):
    """Public view of a domain. Never includes the transfer token."""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DomainAuthInfo(BaseModel):
    """The secret transfer token (authInfo) for a domain.

    Only meant to be requested by the domain's current sponsoring
    registrar, who then shares it out-of-band with whoever wants to
    transfer the domain away (the "losing registrar" flow).
    """

    name: str
    transfer_token: str


class DomainTransferRequest(BaseModel):
    """A pull transfer request submitted by the gaining registrar.

    The transfer only succeeds if `transfer_token` matches the domain's
    current transfer token, which acts as the losing registrar's
    authorization for the transfer.
    """

    gaining_registrar: str = Field(..., min_length=1, max_length=200)
    transfer_token: str = Field(..., min_length=1)


class Registrar(BaseModel):
    """Directory entry for a registrar portal instance.

    Registrars self-register this on startup so the registry can broker
    cross-registrar transfer-authorization redirects: when a losing
    registrar redirects to the registry's fixed transfer callback, the
    registry looks up the requesting (gaining) registrar's own
    `callback_url` here and sends the browser back there.
    """

    name: str = Field(..., min_length=1, max_length=200)
    authorize_url: str = Field(..., min_length=1, max_length=500)
    callback_url: str = Field(..., min_length=1, max_length=500)
