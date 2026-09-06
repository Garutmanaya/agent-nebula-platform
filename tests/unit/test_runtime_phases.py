"""Regression tests for the listener-ready Agent Runtime lifecycle boundary."""

from __future__ import annotations

import pytest

from agent_nebula_platform import (
    AgentRuntime,
    MemoryStateStore,
    NullEventSink,
    RuntimeContext,
)
from agent_nebula_platform.platform.health import HealthStatus
from agent_nebula_platform.platform.plugins import RuntimePlugin, RuntimePluginPhase


class Connector:
    """Provide the minimal connector shape required by RuntimeContext tests."""


class RecordingPlugin(RuntimePlugin):
    """Record lifecycle calls for one explicitly selected runtime phase."""

    def __init__(self, name: str, phase: RuntimePluginPhase, events: list[str]) -> None:
        self._name = name
        self._phase = phase
        self._events = events

    @property
    def name(self) -> str:
        """Return the configured test identifier."""

        return self._name

    @property
    def phase(self) -> RuntimePluginPhase:
        """Return the phase selected by the test."""

        return self._phase

    async def initialize(self, context: RuntimeContext) -> None:
        """Record successful phase initialization."""

        del context
        self._events.append(f"init:{self._name}")

    async def close(self, context: RuntimeContext) -> None:
        """Record reverse-order shutdown."""

        del context
        self._events.append(f"close:{self._name}")

    async def readiness(self) -> HealthStatus:
        """Report readiness for health aggregation tests."""

        return HealthStatus(status="ready", ready=True)


def context() -> RuntimeContext:
    """Create a minimal caller-owned runtime context."""

    return RuntimeContext(Connector(), MemoryStateStore(), NullEventSink())


@pytest.mark.asyncio
async def test_phases_initialize_on_opposite_sides_of_server_boundary() -> None:
    """Post-server plugins remain untouched until listener readiness is signaled."""

    events: list[str] = []
    runtime = AgentRuntime(
        context=context(),
        plugins=(
            RecordingPlugin("routes", RuntimePluginPhase.PRE_SERVER, events),
            RecordingPlugin("onboarding", RuntimePluginPhase.POST_SERVER, events),
        ),
    )

    await runtime.initialize_pre_server()
    assert events == ["init:routes"]

    await runtime.initialize_post_server()
    assert events == ["init:routes", "init:onboarding"]

    await runtime.close()
    assert events[-2:] == ["close:onboarding", "close:routes"]


@pytest.mark.asyncio
async def test_post_server_phase_requires_pre_server_phase() -> None:
    """Reject callback-dependent startup before local endpoints are prepared."""

    runtime = AgentRuntime(
        context=context(),
        plugins=(RecordingPlugin("onboarding", RuntimePluginPhase.POST_SERVER, []),),
    )

    with pytest.raises(Exception, match="Pre-server"):
        await runtime.initialize_post_server()
