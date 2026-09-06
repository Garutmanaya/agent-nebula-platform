"""Integration tests for health aggregation and JSON metrics endpoints."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_nebula_platform import MemoryStateStore, NullEventSink, RuntimeContext
from agent_nebula_platform.platform.health import StaticHealthProvider
from agent_nebula_platform.platform.metrics import MetricsRegistry
from agent_nebula_platform.platform.presets import (
    EmbeddedPresetOptions,
    RuntimeFeatureComponents,
    RuntimePluginSettings,
    build_embedded_runtime,
)


class StubConnector:
    """Minimal connector because operational routes are local-only."""


def test_operational_routes_expose_plugin_health_and_metrics() -> None:
    """The FastAPI adapter returns aggregate health and a metrics snapshot."""

    app = FastAPI()
    metrics = MetricsRegistry()
    metrics.increment("agent.requests")
    runtime = build_embedded_runtime(
        context=RuntimeContext(
            nebula=StubConnector(),
            state_store=MemoryStateStore(),
            events=NullEventSink(),
        ),
        components=RuntimeFeatureComponents.create(
            health=StaticHealthProvider(),
            metrics_registry=metrics,
        ),
        options=EmbeddedPresetOptions(
            app=app,
            plugins=RuntimePluginSettings(metrics=True),
        ),
    )

    asyncio.run(runtime.initialize())
    try:
        with TestClient(app) as client:
            health = client.get("/health")
            metrics_response = client.get("/api/v1/metrics")
        assert health.status_code == 200
        assert health.json()["details"]["host"] == "healthy"
        assert metrics_response.status_code == 200
        assert metrics_response.json()["counters"]["agent.requests"] == 1
    finally:
        asyncio.run(runtime.close())
