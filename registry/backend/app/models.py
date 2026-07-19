"""Pydantic models (schemas) for the registry API."""

from datetime import datetime

from pydantic import BaseModel, Field


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

    Registrars self-register this on startup so other registrars can look
    up where to send a domain owner to authorize a cross-registrar
    transfer (`authorize_url`), and so the registry can verify the signed
    transfer assertions they issue (`public_key`). The losing registrar
    redirects the browser directly back to the gaining registrar
    afterwards, using the `return_url` the gaining registrar supplied in
    its request - the registry is only used as a directory lookup here,
    not as a redirect broker.
    """

    name: str = Field(..., min_length=1, max_length=200)
    authorize_url: str = Field(..., min_length=1, max_length=500)
    public_key: str = Field(
        ..., min_length=1, max_length=4000, description="PEM-encoded RSA public key"
    )
