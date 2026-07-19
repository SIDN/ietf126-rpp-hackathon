"""RSA keypair for signing cross-registrar transfer assertions.

Each registrar instance generates its own keypair at startup and publishes
the public key to the registry directory (alongside its `authorize_url`),
so the registry can verify assertions this registrar signs with its
private key when it acts as the losing (currently-sponsoring) registrar
for a domain transfer.
"""

import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

TRANSFER_OPERATION = "write:transfer"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_key_pem = (
    _private_key.public_key()
    .public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)


def public_key_pem() -> str:
    """This instance's own public key (PEM), to publish to the registry."""
    return _public_key_pem


def sign_transfer_assertion(domain: str, *, issuer: str) -> str:
    """Sign a `write:transfer` assertion for `domain` with this registrar's
    own private key (RS256), proving it (as the domain's current sponsor)
    authorized this exact operation."""
    return jwt.encode(
        {
            "operation": TRANSFER_OPERATION,
            "domain": domain,
            "iss": issuer,
            "iat": int(time.time()),
        },
        _private_key,
        algorithm="RS256",
    )
