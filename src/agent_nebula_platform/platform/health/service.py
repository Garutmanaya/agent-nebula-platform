"""Plugin-level health aggregation for runtime diagnostics and readiness."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable

from .models import HealthProvider, HealthStatus


class RuntimeHealthService:
    """Aggregate host health with every initialized plugin contribution."""

    def __init__(
        self,
        *,
        plugin_supplier: Callable[[], Iterable[object]],
        host_provider: HealthProvider | None = None,
    ) -> None:
        self._plugin_supplier = plugin_supplier
        self._host_provider = host_provider

    def set_host_provider(self, provider: HealthProvider | None) -> None:
        """Attach or replace the host-level health provider before serving traffic."""

        self._host_provider = provider

    async def health(self) -> HealthStatus:
        """Return aggregate liveness across host and plugin contributors."""

        return await self._aggregate(readiness=False)

    async def readiness(self) -> HealthStatus:
        """Return aggregate readiness across host and plugin contributors."""

        return await self._aggregate(readiness=True)

    async def _aggregate(self, *, readiness: bool) -> HealthStatus:
        """Collect components without allowing one diagnostic failure to crash health."""

        details: dict[str, str] = {}
        ready = True
        if self._host_provider is not None:
            value = (
                self._host_provider.readiness()
                if readiness
                else self._host_provider.health()
            )
            if inspect.isawaitable(value):
                value = await value
            details["host"] = value.status
            ready = ready and value.ready
        for plugin in self._plugin_supplier():
            name = str(getattr(plugin, "name", plugin.__class__.__name__))
            try:
                contribution = plugin.readiness() if readiness else plugin.health()
                if inspect.isawaitable(contribution):
                    contribution = await contribution
            except Exception:  # noqa: BLE001 - isolate failures at runtime boundary
                details[name] = "failed"
                ready = False
                continue
            details[name] = contribution.status
            ready = ready and contribution.ready
        return HealthStatus(
            status=("ready" if readiness else "healthy") if ready else "degraded",
            ready=ready,
            details=details,
        )
