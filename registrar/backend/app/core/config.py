"""Application configuration for the registrar portal."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Registrar Portal"
    api_prefix: str = "/api"
    cors_origins: list[str] = [
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

    # Identity of the registrar this portal instance represents. Run
    # multiple instances (with different .env files / ports) to simulate
    # different registrars transferring domains between each other.
    registrar_name: str = "Registrar A"

    # Base URL of the registry API this portal talks to.
    registry_api_url: str = "http://localhost:8000/api"

    # This instance's own externally-reachable base URL (scheme+host+port,
    # no trailing slash/path). Must match the --port this instance actually
    # runs on - used to compute the transfer authorize/complete URLs this
    # registrar self-registers with the registry directory (see
    # api/transfer_routes.py), so other registrars can find them.
    public_base_url: str = "http://localhost:8001"

    # OAuth2/OIDC settings for a *confidential* client (e.g. an Authentik
    # application). The registrar backend - not the browser - authenticates
    # to the provider using client_id + client_secret and performs the
    # authorization code exchange itself. The browser only ever gets an
    # HttpOnly session cookie, never the OAuth2 tokens.
    oauth2_issuer: str = "http://localhost:9991/application/o/registrar/"
    oauth2_client_id: str = ""
    oauth2_client_secret: str = ""
    # Must be registered as a redirect URI on the Authentik provider.
    oauth2_redirect_uri: str = "http://localhost:8001/api/auth/callback"
    # Where to send the browser after a successful login.
    frontend_url: str = "http://localhost:5174/"

    session_cookie_name: str = "registrar_session"
    session_ttl_seconds: int = 3600

    # Logging verbosity (DEBUG, INFO, WARNING, ...). Set to DEBUG to see
    # every URL the registrar backend requests, in or out.
    log_level: str = "INFO"

    class Config:
        env_prefix = ""
        env_file = ".env"

    @property
    def transfer_authorize_url(self) -> str:
        """This registrar's own authorization endpoint (losing-registrar
        side): where other registrars redirect the browser to request a
        transfer of a domain this registrar currently sponsors."""
        return f"{self.public_base_url}{self.api_prefix}/transfer/authorize"

    @property
    def transfer_complete_url(self) -> str:
        """This registrar's own transfer-complete endpoint (gaining-
        registrar side): the fixed callback URL the registry redirects the
        browser back to once a transfer request it started has been
        processed."""
        return f"{self.public_base_url}{self.api_prefix}/transfer/complete"

    @property
    def registry_transfer_callback_url(self) -> str:
        """The registry's fixed transfer callback - the losing registrar
        always redirects here, regardless of which registrar started the
        transfer."""
        return f"{self.registry_api_url}/transfer/callback"


settings = Settings()
