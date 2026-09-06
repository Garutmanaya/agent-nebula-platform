"""Metrics plugin exposing one registry to other runtime capabilities."""

from __future__ import annotations

from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.health import HealthStatus
from agent_nebula_platform.platform.metrics import MetricsRegistry
from agent_nebula_platform.platform.plugins.base import RuntimePlugin


class MetricsPlugin(RuntimePlugin):
    """Register a host-neutral in-process metrics registry."""

    def __init__(
        self, registry: MetricsRegistry | None = None, *, required: bool = False
    ) -> None:
        self._registry = registry or MetricsRegistry()
        self._required = required

    @property
    def name(self) -> str:
        """Return the stable plugin identifier."""

        return "operations.metrics"

    @property
    def required(self) -> bool:
        """Return whether metrics initialization failure is fatal."""

        return self._required

    async def initialize(self, context: RuntimeContext) -> None:
        """Register the metrics registry for transport and plugin collaboration."""

        context.services.register("metrics", self._registry)

    async def close(self, context: RuntimeContext) -> None:
        """Remove the runtime service marker during shutdown."""

        context.services.remove("metrics")

    async def health(self) -> HealthStatus:
        """Report metrics availability without depending on an exporter."""

        return HealthStatus(status="healthy", ready=True)
