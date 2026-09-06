"""Telemetry sink ports and safe built-in console and JSON-lines adapters."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import RLock
from typing import Protocol

from .events import TelemetryEvent


class TelemetrySink(Protocol):
    """Receive one structured telemetry event."""

    async def publish(self, event: TelemetryEvent) -> None:
        """Publish one event without mutating it."""


class ConsoleTelemetrySink:
    """Publish telemetry through a caller-owned logger."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    async def publish(self, event: TelemetryEvent) -> None:
        """Log one event without configuring root logging."""

        level = getattr(logging, event.severity.value.upper())
        self._logger.log(
            level,
            event.event_type,
            extra={"telemetry_event": event.model_dump(mode="json")},
        )


class JsonLinesTelemetrySink:
    """Append telemetry as one JSON document per line to a caller-approved file."""

    def __init__(self, path: Path) -> None:
        """Initialize the sink with an absolute output path and write lock."""

        self._path = path.expanduser().resolve()
        self._lock = RLock()

    async def publish(self, event: TelemetryEvent) -> None:
        """Append one immutable telemetry event as a compact JSON line."""

        document = event.model_dump_json()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(document)
            handle.write("\n")
