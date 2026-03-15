"""Logging configuration."""

import logging
from typing import Final

_LOGGER_NAME: Final = "app"


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    """Get or create logger instance.

    Args:
        name: Logger name (default: app).

    Returns:
        Logger instance.
    """
    logger = logging.getLogger(name)

    # Если handler'ов нет — настраиваем (идемпотентность)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.propagate = False

    return logger


def setup_logger(debug: bool = False) -> logging.Logger:
    """Configure root logger with debug level.

    Args:
        debug: Enable debug level logging.

    Returns:
        Root logger instance.
    """
    level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,  # Пересоздаём handler'ы
    )

    return logging.getLogger(_LOGGER_NAME)
