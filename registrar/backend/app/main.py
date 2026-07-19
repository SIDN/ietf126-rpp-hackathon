"""FastAPI application entry point for the registrar portal."""

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth_routes import router as auth_router
from app.api.routes import router as registrar_router
from app.api.transfer_routes import router as transfer_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app import registry_client, signing

configure_logging()
logger = logging.getLogger("registrar.access")

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every URL requested of this app (method, full URL, status,
    duration) - inbound requests from the frontend or anyone else."""
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "%s %s -> %s (%.1fms)",
        request.method,
        request.url,
        response.status_code,
        duration_ms,
    )
    return response


app.include_router(registrar_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(transfer_router, prefix=settings.api_prefix)


@app.on_event("startup")
async def register_with_registry() -> None:
    """Self-register this registrar's directory entry (its transfer
    authorize URL and public key) with the registry, so other registrars
    can look up where to send a domain owner to authorize a transfer, and
    the registry can verify the signed transfer assertions this registrar
    issues. Best-effort: if the registry isn't up yet, just log a warning
    rather than failing to start.
    """
    try:
        await registry_client.register_registrar(
            settings.registrar_name,
            settings.transfer_authorize_url,
            signing.public_key_pem(),
        )
        logger.info("Registered with registry directory as '%s'", settings.registrar_name)
    except Exception as exc:  # noqa: BLE001 - best-effort, non-fatal
        logger.warning("Failed to register with registry directory: %s", exc)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
