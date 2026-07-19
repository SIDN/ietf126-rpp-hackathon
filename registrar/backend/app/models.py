"""Pydantic models (schemas) for the registrar portal."""

from datetime import datetime

from pydantic import BaseModel


class Domain(BaseModel):
    """A domain as reported by the registry."""

    name: str
    registrar: str
    registrant: str
    created_at: datetime
    updated_at: datetime


class DomainAuthInfo(BaseModel):
    """A domain's transfer token, as reported by the registry."""

    name: str
    transfer_token: str
