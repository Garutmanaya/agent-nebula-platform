"""Optional preset-owned logging composition.

The helper configures only a named runtime logger. It never calls
``logging.basicConfig`` and never modifies the process root logger, allowing a
host application to keep its existing logging policy.
"""

from __future__ import annotations

import logging

from agent_nebula_platform.platform.events import PythonLoggingEventSink


def create_console_event_sink(
    *,
    logger_name: str = "agent_nebula_platform",
    level: int = logging.INFO,
) -> PythonLoggingEventSink:
    """Create an isolated console-backed event sink for standalone agents.

    A handler is added only when the named logger has no handlers. This avoids
    duplicate messages when the composition function is called repeatedly in
    tests or by a development reloader.
    """

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        logger.addHandler(handler)
    return PythonLoggingEventSink(logger)
