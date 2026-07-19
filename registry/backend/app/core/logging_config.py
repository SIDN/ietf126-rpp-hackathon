"""Central logging configuration for the registry"""

import logging

from app.core.config import settings


def configure_logging() -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
    )
