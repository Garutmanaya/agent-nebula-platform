"""Phased lifecycle for pluggable embedded and standalone Agent Runtime use."""

from __future__ import annotations

from collections.abc import Iterable
from time import perf_counter
from typing import Self

from .context import RuntimeContext
from .errors import PluginError
from .events import RuntimeEvent
from .health import RuntimeHealthService
from .metrics import MetricsRegistry
from .plugins.base import RuntimePlugin, RuntimePluginPhase
from .plugins.registry import PluginRegistry, PluginStatus
from .telemetry import TelemetryEvent, TelemetryService, TelemetrySeverity


class AgentRuntime:
    """Initialize plugins on the correct side of the server-ready boundary.

    Local capabilities such as routes, skill registries, Agent Cards, and
    health endpoints initialize before the HTTP listener starts. Capabilities
    such as Agent Nebula onboarding initialize only after the listener reports
    that it is accepting traffic, avoiding the registration callback deadlock.
    """

    def __init__(
        self,
        *,
        context: RuntimeContext,
        plugins: Iterable[RuntimePlugin] = (),
    ) -> None:
        self._context = context
        self._registry = PluginRegistry(plugins)
        self._started: list[RuntimePlugin] = []
        self._initialized_phases: set[RuntimePluginPhase] = set()
        self._health = RuntimeHealthService(
            plugin_supplier=lambda: self._registry.plugins
        )
        if "runtime.health" not in self._context.services.names():
            self._context.services.register("runtime.health", self._health)

    @property
    def context(self) -> RuntimeContext:
        """Return the immutable dependency context."""

        return self._context

    @property
    def plugin_statuses(self) -> dict[str, PluginStatus]:
        """Return current plugin lifecycle states for diagnostics."""

        return self._registry.snapshot()

    async def initialize_pre_server(self) -> None:
        """Initialize plugins that must be available before serving traffic."""

        await self._initialize_phase(RuntimePluginPhase.PRE_SERVER)

    async def initialize_post_server(self) -> None:
        """Initialize plugins that require the HTTPS listener to be reachable."""

        if RuntimePluginPhase.PRE_SERVER not in self._initialized_phases:
            raise PluginError(
                "Pre-server runtime plugins must initialize before post-server plugins"
            )
        await self._initialize_phase(RuntimePluginPhase.POST_SERVER)

    async def initialize(self) -> None:
        """Initialize both phases for compatibility with non-server use.

        Server-owning compositions must call ``initialize_pre_server`` before
        listener startup and ``initialize_post_server`` only after the listener
        is accepting connections. This compatibility method remains useful for
        tests and integrations that have no callback-dependent plugins.
        """

        await self.initialize_pre_server()
        await self.initialize_post_server()

    async def _initialize_phase(self, phase: RuntimePluginPhase) -> None:
        """Initialize one phase in deterministic plugin order."""

        if phase in self._initialized_phases:
            return
        self._context.events.emit(
            RuntimeEvent("runtime.phase.initialization.started", {"phase": phase.value})
        )
        try:
            for plugin in self._registry.plugins:
                if plugin.phase != phase:
                    continue
                await self._initialize_plugin(plugin)
        except Exception:
            await self._close_started()
            self._initialized_phases.clear()
            raise
        self._initialized_phases.add(phase)
        self._context.events.emit(
            RuntimeEvent("runtime.phase.initialized", {"phase": phase.value})
        )
        if phase is RuntimePluginPhase.POST_SERVER:
            self._context.events.emit(RuntimeEvent("runtime.initialized"))

    async def _initialize_plugin(self, plugin: RuntimePlugin) -> None:
        """Initialize one plugin and isolate optional failures."""

        started_at = perf_counter()
        try:
            await plugin.before_start(self._context)
            await plugin.initialize(self._context)
            await plugin.after_start(self._context)
        except Exception as exc:
            self._registry.mark_failed(plugin.name)
            self._context.events.emit(
                RuntimeEvent(
                    "runtime.plugin.initialization_failed",
                    {
                        "plugin": plugin.name,
                        "required": plugin.required,
                        "phase": plugin.phase.value,
                    },
                )
            )
            if plugin.required:
                raise PluginError(
                    f"Required runtime plugin failed: {plugin.name}"
                ) from exc
            return
        self._started.append(plugin)
        self._registry.mark_initialized(plugin.name)
        elapsed = perf_counter() - started_at
        self._record_plugin_start(plugin.name, elapsed)
        await self._publish_telemetry(
            TelemetryEvent(
                event_type="runtime.plugin.initialized",
                plugin=plugin.name,
                attributes={
                    "duration_seconds": elapsed,
                    "phase": plugin.phase.value,
                },
            )
        )
        self._context.events.emit(
            RuntimeEvent(
                "runtime.plugin.initialized",
                {"plugin": plugin.name, "phase": plugin.phase.value},
            )
        )

    async def close(self) -> None:
        """Close post-server and pre-server plugins in reverse start order."""

        await self._close_started()
        self._initialized_phases.clear()
        self._context.events.emit(RuntimeEvent("runtime.closed"))

    async def _close_started(self) -> None:
        """Close started plugins while aggregating shutdown failures."""

        failures: list[tuple[str, Exception]] = []
        while self._started:
            plugin = self._started.pop()
            try:
                await plugin.before_shutdown(self._context)
                await plugin.close(self._context)
                await plugin.after_shutdown(self._context)
            except Exception as exc:  # noqa: BLE001 - isolate failures at runtime boundary
                failures.append((plugin.name, exc))
                self._registry.mark_failed(plugin.name)
                self._context.events.emit(
                    RuntimeEvent("runtime.plugin.close_failed", {"plugin": plugin.name})
                )
            else:
                self._registry.mark_enabled(plugin.name)
        if failures:
            raise PluginError(
                "One or more runtime plugins failed during shutdown"
            ) from failures[0][1]

    def _record_plugin_start(self, plugin_name: str, elapsed: float) -> None:
        """Record plugin startup duration when metrics are enabled."""

        if "metrics" not in self._context.services.names():
            return
        registry = self._context.services.require("metrics", MetricsRegistry)
        registry.increment("runtime.plugin.initialized")
        registry.observe(f"runtime.plugin.startup.{plugin_name}", elapsed)

    async def _publish_telemetry(self, event: TelemetryEvent) -> None:
        """Publish telemetry only when the optional capability is initialized."""

        if "telemetry" not in self._context.services.names():
            return
        service = self._context.services.require("telemetry", TelemetryService)
        failures = await service.publish(event)
        if failures:
            self._context.events.emit(
                RuntimeEvent(
                    "runtime.telemetry.publish_failed",
                    {
                        "failure_count": len(failures),
                        "severity": TelemetrySeverity.WARNING.value,
                    },
                )
            )

    async def __aenter__(self) -> Self:
        """Initialize both phases for async context-manager use."""

        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Close the runtime for async context-manager use."""

        del exc_type, exc, tb
        await self.close()
