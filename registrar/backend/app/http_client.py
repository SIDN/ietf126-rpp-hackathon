"""Shared httpx client factory that logs every outgoing request/response
URL. Used everywhere the registrar backend calls out to another service
(the registry API, the OAuth2 provider) so all such requests show up in
the logs with their full URL.
"""

import logging

import httpx

logger = logging.getLogger("registrar.http")


async def _log_request(request: httpx.Request) -> None:
    logger.info("-> %s %s", request.method, request.url)


async def _log_response(response: httpx.Response) -> None:
    request = response.request
    logger.info("<- %s %s %s", response.status_code, request.method, request.url)


def new_client(**kwargs: object) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient that logs every request it makes."""
    return httpx.AsyncClient(
        event_hooks={"request": [_log_request], "response": [_log_response]},
        **kwargs,
    )
