"""Agent Nebula discovery port, client facade, and execution tracing."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.execution_trace import record_execution_event
from agent_nebula_platform.platform.plugins.base import RuntimePlugin


class DiscoveryPort(Protocol):
    """Transport-neutral discovery operation."""

    async def search(self, parameters: Mapping[str, Any]) -> dict[str, Any]:
        """Search Agent Nebula using caller-defined filters."""
        ...


class NebulaDiscoveryClient:
    """Discovery facade using the composed Agent Nebula connector."""

    def __init__(self, context: RuntimeContext) -> None:
        self._context = context

    async def search(self, parameters: Mapping[str, Any]) -> dict[str, Any]:
        """Delegate one search request while emitting request/response trace events."""

        request_parameters = dict(parameters)
        record_execution_event(
            {
                "type": "DISCOVERY_REQUEST",
                "source": "ORCHESTRATOR",
                "component": "REGISTRY",
                "direction": "REQUEST",
                "target": "AGENT_NEBULA_REGISTRY",
                "status": "STARTED",
                "duration_ms": 0,
                "request": {"parameters": request_parameters},
                "details": {"operation": "agent.discovery"},
            }
        )
        started = time.perf_counter()
        try:
            payload = await self._context.nebula.discover(request_parameters)
        except Exception as exc:
            record_execution_event(
                {
                    "type": "DISCOVERY_RESPONSE",
                    "source": "AGENT_NEBULA",
                    "component": "REGISTRY",
                    "direction": "RESPONSE",
                    "target": "ORCHESTRATOR",
                    "status": "FAILED",
                    "duration_ms": _duration_ms(started),
                    "response": {"error_type": type(exc).__name__},
                    "details": {"operation": "agent.discovery"},
                }
            )
            raise
        record_execution_event(
            {
                "type": "DISCOVERY_RESPONSE",
                "source": "AGENT_NEBULA",
                "component": "REGISTRY",
                "direction": "RESPONSE",
                "target": "ORCHESTRATOR",
                "status": "SUCCEEDED",
                "duration_ms": _duration_ms(started),
                "response": {
                    "agent_count": _discovery_count(payload),
                    "envelope_keys": sorted(payload.keys())
                    if isinstance(payload, Mapping)
                    else [],
                    "body": payload,
                },
                "details": {"operation": "agent.discovery"},
            }
        )
        return payload


class DiscoveryPlugin(RuntimePlugin):
    """Expose a discovery client without starting background work."""

    def __init__(self, *, required: bool = False) -> None:
        self._required = required
        self.client: NebulaDiscoveryClient | None = None

    @property
    def name(self) -> str:
        """Return the stable discovery plugin identifier."""

        return "nebula.discovery"

    @property
    def required(self) -> bool:
        """Return whether discovery initialization is startup-critical."""

        return self._required

    async def initialize(self, context: RuntimeContext) -> None:
        """Create the connector-backed discovery facade."""

        self.client = NebulaDiscoveryClient(context)

    async def close(self, context: RuntimeContext) -> None:
        """Release the discovery facade without closing shared connectors."""

        del context
        self.client = None


def _duration_ms(started: float) -> int:
    """Convert one monotonic start time into a non-negative millisecond duration."""

    return max(0, round((time.perf_counter() - started) * 1000))


def _discovery_count(payload: Any) -> int:
    """Return a safe result count without depending on one discovery envelope shape."""

    if isinstance(payload, Sequence) and not isinstance(
        payload, (str, bytes, bytearray)
    ):
        return len(payload)
    if not isinstance(payload, Mapping):
        return 0
    for key in ("items", "agents", "results"):
        value = payload.get(key)
        if isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            return len(value)
    return (
        1
        if any(key in payload for key in ("agent_id", "id", "external_agent_id"))
        else 0
    )
