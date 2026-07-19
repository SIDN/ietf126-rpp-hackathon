"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Registry API"
    api_prefix: str = "/api"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    class Config:
        env_prefix = "REGISTRY_"

    # Logging verbosity (DEBUG, INFO, WARNING, ...). Set to DEBUG to see
    # every URL the registrar backend requests, in or out.
    log_level: str = "INFO"


settings = Settings()
