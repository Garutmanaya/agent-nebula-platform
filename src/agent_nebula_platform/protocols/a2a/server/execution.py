"""Generic business-handler bridge to the official A2A AgentExecutor contract."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol

from a2a.helpers import get_message_text, new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from google.protobuf.json_format import MessageToDict

from agent_nebula_platform.platform.errors import ConfigurationError

type A2ABusinessResult = Mapping[str, object]
type A2ABusinessHandler = Callable[
    [Mapping[str, object]],
    A2ABusinessResult | Awaitable[A2ABusinessResult],
]

class A2AExecutableSkill(Protocol):
    """Minimal skill contract required by the A2A execution adapter."""

    @property
    def skill_id(self) -> str:
        """Return the stable business skill identifier."""

    @property
    def handler(self) -> A2ABusinessHandler:
        """Return the business handler invoked for an A2A message."""


class A2AAgentExecutor(AgentExecutor):
    """Adapt a protocol-neutral business skill to official A2A execution.

    A2A 1.0 ``SendMessage`` does not carry a standard skill identifier.  This
    adapter therefore executes the skill selected by composition and does not
    invent proprietary message metadata for routing.
    """

    def __init__(self, skill: A2AExecutableSkill) -> None:
        """Bind one already-selected executable skill."""

        self._skill = skill

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Translate an A2A message into the generic business-handler payload."""

        message = context.message
        text = get_message_text(message, delimiter=" ") if message is not None else ""
        payload: dict[str, object] = {"message": text}
        if message is not None:
            for part in message.parts:
                if part.HasField("data"):
                    data = MessageToDict(part.data)
                    if isinstance(data, dict):
                        payload.update(data)
        result = self._skill.handler(payload)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, Mapping):
            raise ConfigurationError(
                f"A2A skill '{self._skill.skill_id}' must return a mapping/dict"
            )
        await event_queue.enqueue_event(new_text_message(self._response_text(result)))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Acknowledge cancellation for stateless business-handler execution."""

        del context, event_queue

    @staticmethod
    def _response_text(result: Mapping[object, object]) -> str:
        """Select a conventional text field while preserving arbitrary mappings."""

        for key in ("message", "text"):
            value = result.get(key)
            if value is not None:
                return str(value)
        return str(dict(result))
