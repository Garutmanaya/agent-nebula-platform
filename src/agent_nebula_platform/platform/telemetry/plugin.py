"""Structured telemetry plugin with sink failure isolation."""

from __future__ import annotations

from collections.abc import Iterable

from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.health import HealthStatus
from agent_nebula_platform.platform.plugins.base import RuntimePlugin
from agent_nebula_platform.platform.telemetry import TelemetryService, TelemetrySink


class TelemetryPlugin(RuntimePlugin):
    """Register a telemetry service composed from caller-approved sinks."""

    def __init__(
        self, sinks: Iterable[TelemetrySink] = (), *, required: bool = False
    ) -> None:
        self._service = TelemetryService(sinks)
        self._required = required

    @property
    def name(self) -> str:
        """Return the stable plugin identifier."""

        return "operations.telemetry"

    @property
    def required(self) -> bool:
        """Return whether telemetry initialization failure is fatal."""

        return self._required

    async def initialize(self, context: RuntimeContext) -> None:
        """Register the telemetry publication service."""

        context.services.register("telemetry", self._service)

    async def close(self, context: RuntimeContext) -> None:
        """Remove the telemetry service marker."""

        context.services.remove("telemetry")

    async def health(self) -> HealthStatus:
        """Report that the in-process telemetry fan-out service is available."""

        return HealthStatus(status="healthy", ready=True)
