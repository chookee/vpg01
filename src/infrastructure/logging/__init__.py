"""Logging configuration with structlog support."""

import logging
import sys
from typing import Any, Final

import structlog

_LOGGER_NAME: Final = "app"


def setup_logger(debug: bool = False) -> logging.Logger:
    """Configure root logger with structlog processors.

    Args:
        debug: Enable debug level logging.

    Returns:
        Root logger instance.
    """
    level = logging.DEBUG if debug else logging.INFO

    # Configure structlog processors
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(
            logging.basicConfig(
                level=level,
                format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                force=True,
                stream=sys.stdout,
            )
        ),
        cache_logger_on_first_use=True,
    )

    return logging.getLogger(_LOGGER_NAME)


def get_logger(name: str = _LOGGER_NAME) -> structlog.BoundLogger:
    """Get or create structlog logger instance.

    Args:
        name: Logger name (default: app).

    Returns:
        Structlog bound logger instance.
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Bind context variables to the logger.

    Args:
        **kwargs: Context variables to bind (e.g., user_id, session_id, trace_id).

    Example:
        bind_context(user_id=123, session_id=456)
        logger.info("message")  # Will include user_id and session_id
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()
