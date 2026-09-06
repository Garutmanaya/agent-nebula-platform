"""Tests for official A2A 1.0 server-interface integration."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from a2a.server.request_handlers import RequestHandler
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from fastapi import FastAPI

from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.protocols.a2a.server.server_adapter import A2AServerAdapter
from agent_nebula_platform.protocols.a2a.server.server_interfaces import (
    A2AServerInterfacePlanner,
)


def _card(*interfaces: AgentInterface) -> AgentCard:
    """Create the smallest valid card needed by transport tests."""

    return AgentCard(
        name="test-agent",
        description="test",
        version="1.0.0",
        supported_interfaces=list(interfaces),
        capabilities=AgentCapabilities(),
        default_input_modes=["text/plain"],
        default_output_modes=["application/json"],
        skills=[AgentSkill(id="test", name="Test", description="test", tags=["test"])],
    )


def test_planner_derives_http_interfaces_from_agent_card() -> None:
    """JSON-RPC and HTTP+JSON paths come exclusively from advertised URLs."""

    plan = A2AServerInterfacePlanner().plan(
        _card(
            AgentInterface(
                url="https://agent.example/a2a/rpc",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            ),
            AgentInterface(
                url="https://agent.example/a2a/rest",
                protocol_binding="HTTP+JSON",
                protocol_version="1.0",
            ),
        )
    )

    assert [(item.binding, item.path) for item in plan.http] == [
        ("JSONRPC", "/a2a/rpc"),
        ("HTTP+JSON", "/a2a/rest"),
    ]
    assert plan.grpc == ()


def test_planner_accepts_official_grpc_authority() -> None:
    """A2A's host:port gRPC interface form becomes a concrete listener."""

    plan = A2AServerInterfacePlanner().plan(
        _card(
            AgentInterface(
                url="127.0.0.1:50051",
                protocol_binding="GRPC",
                protocol_version="1.0",
            )
        )
    )

    assert plan.grpc[0].address == "127.0.0.1:50051"


def test_planner_rejects_unimplemented_binding() -> None:
    """Runtime must never publish an interface for which no adapter exists."""

    with pytest.raises(ConfigurationError, match="unsupported protocol binding"):
        A2AServerInterfacePlanner().plan(
            _card(
                AgentInterface(
                    url="https://agent.example/custom",
                    protocol_binding="CUSTOM",
                    protocol_version="1.0",
                )
            )
        )


@pytest.mark.asyncio
async def test_adapter_mounts_only_configured_http_interfaces() -> None:
    """Official a2a-python routes match the interfaces declared by the card."""

    app = FastAPI()
    adapter = A2AServerAdapter(
        app=app,
        agent_card=_card(
            AgentInterface(
                url="https://agent.example/a2a/rpc",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ),
        request_handler=Mock(spec=RequestHandler),
    )

    await adapter.start()
    paths = {route.path for route in app.routes}

    # The official 1.0.x route factories return Starlette routes. Runtime
    # mounts them directly into the existing FastAPI router.
    assert "/.well-known/agent-card.json" in paths
    assert "/a2a/rpc" in paths
    assert "/a2a/rest/message:send" not in paths
    await adapter.close()
