"""Pydantic models (schemas) for the registrar portal."""

from datetime import datetime

from pydantic import BaseModel, Field


class Domain(BaseModel):
    """A domain as reported by the registry."""

    name: str
    registrar: str
    created_at: datetime
    updated_at: datetime


class DomainAuthInfo(BaseModel):
    """A domain's transfer token, as reported by the registry."""

    name: str
    transfer_token: str


class TransferRequest(BaseModel):
    """A pull transfer request: pull `domain_name` to this registrar using
    the transfer token provided by the domain's current sponsor."""

    domain_name: str = Field(..., min_length=1, max_length=253)
    transfer_token: str = Field(..., min_length=1)
