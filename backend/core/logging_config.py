"""
core/logging_config.py
======================
Structured logging configuration for SemanticStream using structlog.

Provides a factory function ``get_logger`` that returns a bound structlog
logger.  All log output is emitted as structured JSON in production and as
coloured console output in debug mode.

Usage:
    from backend.core.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("message", key="value")
"""

import logging
import sys
from typing import Any

import structlog

from backend.core.config import settings


def configure_logging() -> None:
    """Configure structlog and stdlib logging once at application startup.

    This must be called exactly once, from ``main.py``, before any other
    module imports or uses ``get_logger``.
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.LOG_JSON:
        # Production: machine-readable JSON
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: human-friendly coloured output
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *shared_processors,
            renderer,
        ]
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(settings.LOG_LEVEL.upper())

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "multipart", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given module name.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A structlog ``BoundLogger`` instance bound to the given name.
    """
    return structlog.get_logger(name)
