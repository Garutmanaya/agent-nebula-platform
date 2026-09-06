"""FastAPI A2UI capability and negotiation route tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_nebula_platform import (
    AgentRuntime,
    MemoryStateStore,
    NullEventSink,
    RuntimeContext,
)
from agent_nebula_platform.a2ui import A2UIActionBinding
from agent_nebula_platform.a2ui.plugin import A2UIPlugin
from agent_nebula_platform.platform.lifecycle.agent_server_plugin import (
    AgentServerPlugin,
)
from agent_nebula_platform.platform.transport.fastapi import runtime_lifespan
from agent_nebula_platform.skills import SkillDefinition, SkillInvocation, SkillResult
from agent_nebula_platform.skills.plugin import SkillsPlugin


class Nebula:
    """Minimal connector because these routes do not call Agent Nebula."""

    async def close(self) -> None:
        """Satisfy the Runtime connector lifecycle contract."""


def _app() -> FastAPI:
    """Build an application exposing the stabilized A2UI routes."""

    async def submit(_invocation: SkillInvocation) -> SkillResult:
        return SkillResult(data={"ok": True})

    app = FastAPI()
    runtime = AgentRuntime(
        context=RuntimeContext(
            nebula=Nebula(),  # type: ignore[arg-type]
            state_store=MemoryStateStore(),
            events=NullEventSink(),
        ),
        plugins=(
            SkillsPlugin(
                definitions=(SkillDefinition(skill_id="submit.skill", handler=submit),)
            ),
            A2UIPlugin(
                allowed_components=("Column", "Button"),
                allowed_catalog_ids=("urn:agent-nebula:a2ui:test",),
                action_bindings=(
                    A2UIActionBinding(
                        action_name="submit",
                        skill_id="submit.skill",
                    ),
                ),
            ),
            AgentServerPlugin(app=app, enable_a2ui=True),
        ),
    )
    app.router.lifespan_context = runtime_lifespan(runtime)
    return app


def test_a2ui_capability_and_negotiation_routes() -> None:
    """A renderer can inspect and negotiate the runtime contract over HTTP."""

    with TestClient(_app()) as client:
        capabilities = client.get("/api/v1/a2ui/capabilities")
        negotiated = client.post(
            "/api/v1/a2ui/negotiate",
            json={
                "supported_versions": ["v0.9.1"],
                "supported_components": ["Button"],
                "supported_functions": [],
            },
        )

    assert capabilities.status_code == 200
    assert capabilities.json()["preferred_version"] == "v0.9.1"
    assert capabilities.json()["action_names"] == ["submit"]
    assert negotiated.status_code == 200
    assert negotiated.json()["components"] == ["Button"]
