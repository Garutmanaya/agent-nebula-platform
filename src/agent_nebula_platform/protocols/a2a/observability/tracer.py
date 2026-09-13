"""Pluggable A2A protocol trace sinks.

Tracing is disabled by default.  Development deployments can set
``ANU_A2A_PROTOCOL_TRACE=true``.  Full normalized protocol documents are emitted
only when ``ANU_A2A_PROTOCOL_TRACE_PAYLOADS=true`` is also set; secrets are still
redacted recursively.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Protocol

from .events import A2AProtocolTraceEvent
from .redaction import redact_protocol_value

_TRACE_ENV = "ANU_A2A_PROTOCOL_TRACE"
_PAYLOAD_ENV = "ANU_A2A_PROTOCOL_TRACE_PAYLOADS"
_LOGGER_NAME = "agent_nebula_platform.protocols.a2a.trace"


class _A2AProtocolTraceHandler(logging.StreamHandler):
    """Dedicated console sink for explicitly enabled A2A protocol traces."""



class A2AProtocolTracer(Protocol):
    """Small replaceable interface used by A2A adapters at protocol boundaries."""

    @property
    def include_payloads(self) -> bool:
        """Return whether normalized protocol payloads may be attached to events."""

    def emit(self, event: A2AProtocolTraceEvent) -> None:
        """Publish one structured protocol trace event."""


class NoOpA2AProtocolTracer:
    """Production-default tracer that performs no logging or payload processing."""

    @property
    def include_payloads(self) -> bool:
        """Never request payload materialization when tracing is disabled."""

        return False

    def emit(self, event: A2AProtocolTraceEvent) -> None:
        """Discard one event without side effects."""

        del event


class LoggingA2AProtocolTracer:
    """Write redacted structured protocol events to an isolated Python logger."""

    def __init__(self, *, include_payloads: bool = False) -> None:
        """Create a logger-backed tracer with explicit payload visibility policy."""

        self._include_payloads = include_payloads
        self._logger = logging.getLogger(_LOGGER_NAME)
        # Protocol tracing is an explicit development opt-in.  The trace logger
        # therefore owns both its INFO threshold and one dedicated console sink.
        # Client-only applications (for example an orchestrator launched directly
        # with Uvicorn) do not necessarily install Platform's standalone logging
        # handlers, so relying on parent/root handlers can silently discard enabled
        # client traces.  Disable propagation to prevent duplicate records in
        # Platform-hosted server processes that already have a parent handler.
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._ensure_console_handler()

    def _ensure_console_handler(self) -> None:
        """Install exactly one Platform-owned trace sink on the dedicated logger."""

        if any(isinstance(handler, _A2AProtocolTraceHandler) for handler in self._logger.handlers):
            return
        self._logger.addHandler(_A2AProtocolTraceHandler())

    @property
    def include_payloads(self) -> bool:
        """Return whether callers should include normalized protocol documents."""

        return self._include_payloads

    def emit(self, event: A2AProtocolTraceEvent) -> None:
        """Redact and log one event as deterministic single-line JSON."""

        document = {
            "event": event.name,
            "direction": event.direction,
            **event.fields,
        }
        self._logger.info(
            "A2A_PROTOCOL_TRACE %s",
            json.dumps(
                redact_protocol_value(document),
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ),
        )


def create_protocol_tracer_from_environment() -> A2AProtocolTracer:
    """Create the default tracer from explicit development environment switches."""

    if not _environment_flag(_TRACE_ENV):
        return NoOpA2AProtocolTracer()
    return LoggingA2AProtocolTracer(include_payloads=_environment_flag(_PAYLOAD_ENV))


def _environment_flag(name: str) -> bool:
    """Interpret one opt-in environment flag using strict common boolean values."""

    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
