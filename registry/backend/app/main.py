"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.domains import router as domains_router
from app.api.registrars import router as registrars_router
from app.api.routes import router as entries_router
from app.core.config import settings
from app.models import DomainCreate
from app.store import DomainAlreadyExistsError, domain_store

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(entries_router, prefix=settings.api_prefix)
app.include_router(domains_router, prefix=settings.api_prefix)
app.include_router(registrars_router, prefix=settings.api_prefix)


@app.on_event("startup")
def seed_demo_domains() -> None:
    """Seed a couple of demo domains so the transfer flow can be tried out."""
    demo_domains = [
        DomainCreate(name="example.com", registrar="Registrar A"),
        DomainCreate(name="example.org", registrar="Registrar B"),
    ]
    for domain in demo_domains:
        try:
            domain_store.create(domain)
        except DomainAlreadyExistsError:
            pass


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
