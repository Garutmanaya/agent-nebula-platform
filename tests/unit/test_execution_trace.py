"""Structured execution-trace contracts for Runtime network operations."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent_nebula_platform.platform.discovery import NebulaDiscoveryClient
from agent_nebula_platform.platform.execution_trace import (
    activate_execution_trace,
    record_execution_event,
    reset_execution_trace,
)


def test_execution_trace_recursively_redacts_security_artifacts() -> None:
    """Runtime must redact nested security artifacts before host callbacks run."""

    observed: list[dict] = []
    token = activate_execution_trace("ex-redaction", recorder=observed.append)
    try:
        record_execution_event(
            {
                "type": "TEST",
                "request": {
                    "headers": {"Authorization": "Bearer secret", "X-Test": "safe"},
                    "client_assertion": "jwt",
                },
            }
        )
    finally:
        reset_execution_trace(token)

    assert observed[0]["request"]["headers"]["Authorization"] == "<redacted>"
    assert observed[0]["request"]["headers"]["X-Test"] == "safe"
    assert observed[0]["request"]["client_assertion"] == "<redacted>"


@pytest.mark.asyncio
async def test_discovery_emits_request_and_response_events() -> None:
    """One registry search should expose separate correlated request/response steps."""

    class FakeNebula:
        async def discover(self, parameters):
            assert parameters["q"] == "parking"
            return {"items": [{"agent_id": "agent-1"}, {"agent_id": "agent-2"}]}

    observed: list[dict] = []
    token = activate_execution_trace("ex-discovery", recorder=observed.append)
    try:
        client = NebulaDiscoveryClient(SimpleNamespace(nebula=FakeNebula()))
        await client.search({"q": "parking", "limit": 20})
    finally:
        reset_execution_trace(token)

    assert [event["type"] for event in observed] == [
        "DISCOVERY_REQUEST",
        "DISCOVERY_RESPONSE",
    ]
    assert observed[0]["direction"] == "REQUEST"
    assert observed[1]["direction"] == "RESPONSE"
    assert observed[1]["response"]["agent_count"] == 2
