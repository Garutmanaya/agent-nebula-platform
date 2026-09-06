"""Fan-out telemetry service with sink failure isolation."""

from __future__ import annotations

from collections.abc import Iterable

from .events import TelemetryEvent
from .sinks import TelemetrySink


class TelemetryService:
    """Publish structured events to all configured sinks."""

    def __init__(self, sinks: Iterable[TelemetrySink] = ()) -> None:
        self._sinks = tuple(sinks)

    async def publish(self, event: TelemetryEvent) -> tuple[Exception, ...]:
        """Publish to every sink and return isolated sink failures."""

        failures: list[Exception] = []
        for sink in self._sinks:
            try:
                await sink.publish(event)
            except Exception as exc:  # noqa: BLE001  # pragma: no cover - defensive sink isolation
                failures.append(exc)
        return tuple(failures)
