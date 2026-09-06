"""Runtime event contracts and non-invasive logging adapters."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    """One non-secret runtime lifecycle or integration event."""

    name: str
    attributes: Mapping[str, Any] = field(default_factory=dict)


class EventSink(Protocol):
    """Receive semantic runtime events without prescribing a logging stack."""

    def emit(self, event: RuntimeEvent) -> None:
        """Publish one event."""


class NullEventSink:
    """Discard events for hosts that do not require runtime telemetry."""

    def emit(self, event: RuntimeEvent) -> None:
        """Discard the supplied event."""
        del event


class PythonLoggingEventSink:
    """Bridge runtime events into a caller-owned Python logger."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def emit(self, event: RuntimeEvent) -> None:
        """Log an event with deterministic, non-secret attributes.

        Runtime event attributes are part of the semantic event contract. Adding
        them to the rendered message keeps ordinary console logs useful even
        when the caller's formatter does not expose ``LogRecord.extra`` values.
        """

        attributes = dict(event.attributes)
        suffix = "".join(f" {name}={attributes[name]}" for name in sorted(attributes))
        self._logger.info(
            f"{event.name}{suffix}",
            extra={"runtime_event": attributes},
        )
