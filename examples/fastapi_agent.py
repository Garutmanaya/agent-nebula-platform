"""Minimal embedded FastAPI agent using Checkpoint 3 runtime capabilities."""

from __future__ import annotations

from fastapi import FastAPI

from agent_nebula_platform import AgentRuntime, MemoryStateStore, NullEventSink, RuntimeContext
from agent_nebula_platform.agent_card import StaticAgentCardProvider
from agent_nebula_platform.platform.health import StaticHealthProvider
from agent_nebula_platform.platform.lifecycle.agent_server_plugin import AgentServerPlugin
from agent_nebula_platform.skills.plugin import SkillsPlugin
from agent_nebula_platform.security.oauth.metadata import StaticProtectedResourceMetadataProvider
from agent_nebula_platform.skills import SkillDefinition, SkillInvocation, SkillResult
from agent_nebula_platform.platform.transport.fastapi import runtime_lifespan


async def echo(invocation: SkillInvocation) -> SkillResult:
    """Return the supplied payload without requiring OAuth scopes."""

    return SkillResult(data={"echo": invocation.payload})


class NoopNebulaConnector:
    """Example-only connector for a server that does not enable Nebula plugins."""


context = RuntimeContext(
    nebula=NoopNebulaConnector(),  # type: ignore[arg-type]
    state_store=MemoryStateStore(),
    events=NullEventSink(),
)
card = StaticAgentCardProvider(
    {
        "id": "echo-agent",
        "name": "Echo Agent",
        "skills": [{"id": "echo", "required_scopes": []}],
    }
)
resource = StaticProtectedResourceMetadataProvider(
    {
        "resource": "https://echo.example.test",
        "authorization_servers": ["https://nebula.example.test"],
        "scopes_supported": [],
    }
)
app = FastAPI()
runtime = AgentRuntime(
    context=context,
    plugins=[
        SkillsPlugin(definitions=[SkillDefinition(skill_id="echo", handler=echo)]),
        AgentServerPlugin(
            app=app,
            agent_card=card,
            protected_resource_metadata=resource,
            health=StaticHealthProvider(),
        ),
    ],
)
app.router.lifespan_context = runtime_lifespan(runtime)
