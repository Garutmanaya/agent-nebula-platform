"""Skill registry and scope-validation tests."""

from __future__ import annotations

import pytest

from agent_nebula_platform import MemoryStateStore, NullEventSink, RuntimeContext
from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.security.oauth.metadata import (
    StaticProtectedResourceMetadataProvider,
)
from agent_nebula_platform.skills import (
    SkillDefinition,
    SkillInvocation,
    SkillRegistry,
    SkillResult,
)
from agent_nebula_platform.skills.plugin import SkillsPlugin


async def _handler(invocation: SkillInvocation) -> SkillResult:
    return SkillResult(data={"skill": invocation.skill_id, **invocation.payload})


@pytest.mark.asyncio
async def test_registry_dispatches_async_handler() -> None:
    registry = SkillRegistry(
        (SkillDefinition(skill_id="demo.search", handler=_handler),)
    )

    result = await registry.invoke(
        SkillInvocation(skill_id="demo.search", payload={"query": "IAD"})
    )

    assert result.data == {"skill": "demo.search", "query": "IAD"}


def test_registry_rejects_duplicate_skill_ids() -> None:
    definition = SkillDefinition(skill_id="demo.search", handler=_handler)

    with pytest.raises(ConfigurationError):
        SkillRegistry((definition, definition))


@pytest.mark.asyncio
async def test_skills_plugin_rejects_scope_absent_from_resource_metadata() -> None:
    plugin = SkillsPlugin(
        definitions=[
            SkillDefinition(
                skill_id="demo.search",
                required_scopes=("demo.search",),
                handler=_handler,
            )
        ],
        metadata_provider=StaticProtectedResourceMetadataProvider(
            {"resource": "https://demo.test", "scopes_supported": ["demo.read"]}
        ),
    )

    class Nebula:
        async def close(self) -> None:
            return None

    context = RuntimeContext(
        nebula=Nebula(),  # type: ignore[arg-type]
        state_store=MemoryStateStore(),
        events=NullEventSink(),
    )
    with pytest.raises(ConfigurationError) as exc_info:
        await plugin.initialize(context)

    assert exc_info.value.details["missing_scopes"] == ["demo.search"]
