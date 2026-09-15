"""Centralized logging configuration.

Logs go to stdout under the ``postharvest`` logger namespace so the
application works both in development and inside containers (Docker).
"""
from __future__ import annotations

import logging
import sys

_LOGGER_NAME = "postharvest"
_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root application logger exactly once."""
    global _configured
    if _configured:
        return

    root = logging.getLogger(_LOGGER_NAME)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                "%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(handler)
    else:
        handler = root.handlers[0]
    root.setLevel(level)
    root.propagate = False
    _configured = True

    # Also wire up the scraper loggers so their output is visible
    scraper_root = logging.getLogger("scraper")
    scraper_root.setLevel(level)
    if not scraper_root.handlers:
        scraper_root.addHandler(handler)
    scraper_root.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced child logger, e.g. get_logger("services.job_service")."""
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")