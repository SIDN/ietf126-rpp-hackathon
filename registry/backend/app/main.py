"""FastAPI application entry point."""

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.domains import router as domains_router
from app.api.registrars import router as registrars_router
from app.core.config import settings
from app.models import DomainCreate
from app.store import DomainAlreadyExistsError, domain_store
from app.core.logging_config import configure_logging

configure_logging()
logger = logging.getLogger("registry.access")

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

app.include_router(domains_router, prefix=settings.api_prefix)
app.include_router(registrars_router, prefix=settings.api_prefix)


@app.on_event("startup")
def seed_demo_domains() -> None:
    """Seed a couple of demo domains so the transfer flow can be tried out."""
    demo_domains = [
        DomainCreate(name="coyote1.example", registrar="Registrar A"),
        DomainCreate(name="coyote2.example", registrar="Registrar A"),
        DomainCreate(name="coyote3.example", registrar="Registrar A"),
        DomainCreate(name="roadrunner1.example", registrar="Registrar B"),
        DomainCreate(name="roadrunner2.example", registrar="Registrar B"),
        DomainCreate(name="roadrunner3.example", registrar="Registrar B"),
    ]
    for domain in demo_domains:
        try:
            domain_store.create(domain)
        except DomainAlreadyExistsError:
            pass


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
