"""A2UI renderer events and A2A AgentSkill invocation use distinct dispatch paths."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from a2a.types import Message, Role

from agent_nebula_platform.a2ui.models import A2UIActionRequest
from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.protocols.a2a.extensions.a2ui.parts import create_a2ui_action_part
from agent_nebula_platform.protocols.a2a.server.execution import A2AAgentExecutor


@dataclass(frozen=True)
class _Skill:
    skill_id: str
    handler: object


class _Context:
    def __init__(self, message: Message) -> None:
        self.message = message
        self.metadata = {}
        self.requested_extensions: set[str] = set()


class _Queue:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def enqueue_event(self, event: object) -> None:
        self.events.append(event)


def _action_message() -> Message:
    action = A2UIActionRequest(
        name="sortResults",
        surface_id="surface-1",
        source_component_id="sort-button",
        timestamp=datetime.now(timezone.utc),
        context={"direction": "ascending"},
    )
    return Message(
        message_id="message-1",
        role=Role.ROLE_USER,
        parts=[create_a2ui_action_part(action)],
    )


@pytest.mark.asyncio
async def test_a2ui_action_bypasses_multiskill_selection() -> None:
    invoked_skills: list[str] = []
    received_actions: list[str] = []

    def skill_handler(_payload):
        invoked_skills.append("unexpected")
        return {"message": "skill"}

    async def action_handler(action, _payload):
        received_actions.append(action.name)
        return {"message": "event"}

    executor = A2AAgentExecutor(
        (
            _Skill("search", skill_handler),
            _Skill("seat-map", skill_handler),
        ),
        a2ui_action_handler=action_handler,
    )
    queue = _Queue()

    await executor.execute(_Context(_action_message()), queue)

    assert received_actions == ["sortResults"]
    assert invoked_skills == []
    assert len(queue.events) == 1


@pytest.mark.asyncio
async def test_a2ui_action_does_not_fall_back_to_single_skill() -> None:
    invoked_skills: list[str] = []

    def skill_handler(_payload):
        invoked_skills.append("unexpected")
        return {"message": "skill"}

    executor = A2AAgentExecutor((_Skill("search", skill_handler),))

    with pytest.raises(ConfigurationError, match="no A2UI action handler"):
        await executor.execute(_Context(_action_message()), _Queue())

    assert invoked_skills == []
