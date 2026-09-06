"""Unit tests for Checkpoint 9 operational runtime capabilities."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from agent_nebula_platform import (
    AgentRuntime,
    MemoryStateStore,
    NullEventSink,
    RuntimeContext,
)
from agent_nebula_platform.platform.health import HealthStatus, RuntimeHealthService
from agent_nebula_platform.platform.metrics import MetricsRegistry
from agent_nebula_platform.platform.metrics.plugin import MetricsPlugin
from agent_nebula_platform.platform.plugins import RuntimePlugin
from agent_nebula_platform.platform.retry import (
    BackoffStrategy,
    RetryPolicy,
    execute_with_retry,
)
from agent_nebula_platform.platform.scheduler import JobTriggerType, ScheduledJob
from agent_nebula_platform.platform.scheduler.plugin import SchedulerPlugin
from agent_nebula_platform.platform.telemetry import (
    JsonLinesTelemetrySink,
    TelemetryEvent,
    TelemetryService,
)
from agent_nebula_platform.platform.telemetry.plugin import TelemetryPlugin


class StubConnector:
    """Minimal connector because operational tests do not perform network calls."""


class HealthPlugin(RuntimePlugin):
    """Plugin with configurable readiness for aggregation tests."""

    def __init__(self, name: str, ready: bool) -> None:
        self._name = name
        self._ready = ready

    @property
    def name(self) -> str:
        """Return the configured plugin name."""

        return self._name

    async def initialize(self, context: RuntimeContext) -> None:
        """Initialize without registering another service."""

        del context

    async def health(self) -> HealthStatus:
        """Return the configured health contribution."""

        return HealthStatus(
            status="healthy" if self._ready else "degraded", ready=self._ready
        )


@pytest.mark.asyncio
async def test_runtime_health_aggregates_plugin_status() -> None:
    """One degraded plugin makes aggregate health fail closed."""

    plugins = [HealthPlugin("ok", True), HealthPlugin("bad", False)]
    service = RuntimeHealthService(plugin_supplier=lambda: plugins)

    result = await service.health()

    assert result.ready is False
    assert result.details == {"ok": "healthy", "bad": "degraded"}


def test_metrics_registry_returns_defensive_snapshot() -> None:
    """Counters, gauges, and timings retain their distinct semantics."""

    registry = MetricsRegistry()
    registry.increment("skills.invoked", 2)
    registry.set_gauge("tasks.depth", 4)
    registry.observe("skills.duration", 0.25)
    registry.observe("skills.duration", 0.75)

    snapshot = registry.snapshot()

    assert snapshot.counters["skills.invoked"] == 2
    assert snapshot.gauges["tasks.depth"] == 4
    assert snapshot.timings["skills.duration"].count == 2
    assert snapshot.timings["skills.duration"].total_seconds == 1.0


@pytest.mark.asyncio
async def test_retry_executor_retries_only_within_policy() -> None:
    """Retry execution stops after the first successful bounded attempt."""

    attempts = 0
    delays: list[float] = []

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("transient")
        return "ok"

    async def sleeper(delay: float) -> None:
        delays.append(delay)

    result = await execute_with_retry(
        operation,
        policy=RetryPolicy(
            max_attempts=3,
            initial_delay_seconds=1,
            strategy=BackoffStrategy.LINEAR,
            jitter_ratio=0,
        ),
        sleeper=sleeper,
    )

    assert result == "ok"
    assert attempts == 3
    assert delays == [1, 2]


@pytest.mark.asyncio
async def test_scheduler_runs_startup_interval_and_shutdown_jobs() -> None:
    """Scheduler starts loops and cancels them before shutdown jobs run."""

    events: list[str] = []

    async def startup() -> None:
        events.append("startup")

    async def interval() -> None:
        events.append("interval")

    async def shutdown() -> None:
        events.append("shutdown")

    context = RuntimeContext(
        nebula=StubConnector(),
        state_store=MemoryStateStore(),
        events=NullEventSink(),
    )
    plugin = SchedulerPlugin(
        (
            ScheduledJob("start", startup, JobTriggerType.STARTUP),
            ScheduledJob(
                "tick", interval, JobTriggerType.INTERVAL, interval_seconds=0.01
            ),
            ScheduledJob("stop", shutdown, JobTriggerType.SHUTDOWN),
        )
    )
    runtime = AgentRuntime(context=context, plugins=(plugin,))

    await runtime.initialize()
    await asyncio.sleep(0.03)
    await runtime.close()

    assert events[0] == "startup"
    assert "interval" in events
    assert events[-1] == "shutdown"


@pytest.mark.asyncio
async def test_json_telemetry_sink_writes_one_document_per_line(tmp_path: Path) -> None:
    """JSON-lines telemetry remains machine-readable and append-only."""

    path = tmp_path / "telemetry.jsonl"
    service = TelemetryService((JsonLinesTelemetrySink(path),))

    failures = await service.publish(TelemetryEvent(event_type="runtime.started"))

    assert failures == ()
    assert '"event_type":"runtime.started"' in path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_runtime_records_plugin_metrics_and_telemetry() -> None:
    """Operational plugins receive startup instrumentation from the runtime."""

    published: list[TelemetryEvent] = []

    class Sink:
        """Collect telemetry events for one test."""

        async def publish(self, event: TelemetryEvent) -> None:
            """Store the immutable event."""

            published.append(event)

    metrics = MetricsRegistry()
    context = RuntimeContext(
        nebula=StubConnector(),
        state_store=MemoryStateStore(),
        events=NullEventSink(),
    )
    runtime = AgentRuntime(
        context=context,
        plugins=(
            MetricsPlugin(metrics),
            TelemetryPlugin((Sink(),)),
            HealthPlugin("sample", True),
        ),
    )

    await runtime.initialize()
    try:
        snapshot = metrics.snapshot()
        assert snapshot.counters["runtime.plugin.initialized"] >= 2
        assert any(
            event.event_type == "runtime.plugin.initialized" for event in published
        )
    finally:
        await runtime.close()
