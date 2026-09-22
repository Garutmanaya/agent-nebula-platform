"""Dependency-light common logging helpers.

This module intentionally depends only on the Python standard library so it can
be imported by protocol adapters and Platform composition code without creating
cross-layer import cycles.
"""

from __future__ import annotations

import logging
import time


LOG_FORMAT = "%(asctime)s.%(msecs)03dZ | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class UTCFormatter(logging.Formatter):
    """Format timestamps in UTC for cross-process/container correlation."""

    converter = time.gmtime


def create_utc_formatter() -> logging.Formatter:
    """Create the common UTC ISO-8601 console formatter used by Platform."""

    return UTCFormatter(LOG_FORMAT, datefmt=DATE_FORMAT)


def configure_console_logger(*, logger_name: str, level: int) -> logging.Logger:
    """Configure one isolated console logger consistently."""

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        handler.setFormatter(create_utc_formatter())
        logger.addHandler(handler)
    else:
        for handler in logger.handlers:
            handler.setLevel(level)
            handler.setFormatter(create_utc_formatter())
    return logger
