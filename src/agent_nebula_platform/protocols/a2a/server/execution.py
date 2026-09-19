"""Generic business-handler bridge to the official A2A AgentExecutor contract."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol

from a2a.helpers import get_message_text
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from google.protobuf.json_format import MessageToDict

from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.a2ui.models import A2UIActionRequest
from agent_nebula_platform.protocols.a2a.extensions.a2ui.parts import parse_a2ui_action_part
from agent_nebula_platform.protocols.a2a.extensions.a2ui.observability import (
    summarize_a2ui_message_metadata,
    summarize_a2ui_parts,
)
from agent_nebula_platform.protocols.a2a.observability import A2AProtocolTraceEvent, A2AProtocolTracer
from agent_nebula_platform.protocols.a2a.observability.tracer import create_protocol_tracer_from_environment
from agent_nebula_platform.skills import SkillResult

from .result_mapper import A2AResultMapper

type A2ABusinessResult = Mapping[str, object] | SkillResult
type A2ABusinessHandler = Callable[
    [Mapping[str, object]],
    A2ABusinessResult | Awaitable[A2ABusinessResult],
]
type A2UIActionHandler = Callable[
    [A2UIActionRequest, Mapping[str, object]],
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
    """Dispatch official A2A messages to registered deterministic business skills.

    NEBULA A2A EXTENSION: A2A core does not define a ``skill_id`` field on
    SendMessageRequest. Multi-skill SecureAgent providers therefore use the
    formal Agent Nebula skill-selection extension. The client selects an
    advertised AgentSkill.id; this executor only validates and dispatches that
    explicit selection. It never performs natural-language or LLM routing.
    """

    def __init__(
        self,
        skills: tuple[A2AExecutableSkill, ...],
        *,
        result_mapper: A2AResultMapper | None = None,
        protocol_tracer: A2AProtocolTracer | None = None,
        a2ui_action_handler: A2UIActionHandler | None = None,
    ) -> None:
        """Bind executable skills by their stable advertised identifiers."""

        if not skills:
            raise ConfigurationError("A2A AgentExecutor requires at least one skill")
        self._skills = {skill.skill_id: skill for skill in skills}
        self._protocol_tracer = protocol_tracer or create_protocol_tracer_from_environment()
        self._a2ui_action_handler = a2ui_action_handler
        self._result_mapper = result_mapper or A2AResultMapper(
            protocol_tracer=self._protocol_tracer
        )
        if len(self._skills) != len(skills):
            raise ConfigurationError("A2A AgentExecutor skill identifiers must be unique")

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Classify the A2A message before dispatching protocol-specific behavior.

        A2UI renderer actions are A2UI protocol messages transported inside an
        official A2A DataPart. They are not AgentSkill invocations and therefore
        must never pass through the Nebula skill-selection extension.
        """

        message = context.message
        self._trace_incoming_request(message)
        a2ui_action, payload = self._parse_message(message)
        if a2ui_action is not None:
            await self._execute_a2ui_action(
                action=a2ui_action,
                payload=payload,
                event_queue=event_queue,
            )
            return
        await self._execute_skill(
            context=context,
            payload=payload,
            event_queue=event_queue,
        )

    def _parse_message(
        self, message: object | None
    ) -> tuple[A2UIActionRequest | None, dict[str, object]]:
        """Separate A2UI renderer actions from ordinary A2A business payloads."""

        text = get_message_text(message, delimiter=" ") if message is not None else ""
        payload: dict[str, object] = {"message": text}
        if message is None:
            return None, payload

        a2ui_action: A2UIActionRequest | None = None
        for part in message.parts:
            parsed_action = parse_a2ui_action_part(part)
            if parsed_action is not None:
                if a2ui_action is not None:
                    raise ConfigurationError("A2A message may contain only one A2UI action")
                a2ui_action = parsed_action
                continue
            if part.HasField("data"):
                data = MessageToDict(part.data)
                if isinstance(data, dict):
                    payload.update(data)

        if a2ui_action is not None:
            metadata = MessageToDict(message.metadata) if message.HasField("metadata") else {}
            renderer_model = metadata.get("a2uiRendererDataModel")
            if isinstance(renderer_model, dict):
                payload["a2ui_renderer_data_model"] = renderer_model
        return a2ui_action, payload

    async def _execute_a2ui_action(
        self,
        *,
        action: A2UIActionRequest,
        payload: Mapping[str, object],
        event_queue: EventQueue,
    ) -> None:
        """Dispatch one A2UI event without applying A2A AgentSkill selection."""

        if self._a2ui_action_handler is None:
            raise ConfigurationError(
                "A2UI renderer action received but no A2UI action handler is configured"
            )
        result = self._a2ui_action_handler(action, payload)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, (Mapping, SkillResult)):
            raise ConfigurationError(
                "A2UI action handler must return a mapping/dict or SkillResult"
            )
        await event_queue.enqueue_event(self._result_mapper.map(result))

    async def _execute_skill(
        self,
        *,
        context: RequestContext,
        payload: Mapping[str, object],
        event_queue: EventQueue,
    ) -> None:
        """Dispatch an ordinary A2A business message to its selected AgentSkill."""

        # NEBULA A2A EXTENSION: skill selection applies only to ordinary A2A
        # business invocation. A2UI renderer events are classified and dispatched
        # before this boundary.
        from agent_nebula_platform.protocols.a2a.extensions import selected_skill_id

        skill_id = selected_skill_id(
            metadata=context.metadata,
            requested_extensions=context.requested_extensions,
        )
        if skill_id is None:
            if len(self._skills) != 1:
                raise ConfigurationError(
                    "Multi-skill A2A agent requires the Nebula skill-selection extension"
                )
            skill = next(iter(self._skills.values()))
        else:
            skill = self._skills.get(skill_id)
            if skill is None:
                raise ConfigurationError(
                    f"Selected A2A skill is not registered: {skill_id}"
                )

        result = skill.handler(payload)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, (Mapping, SkillResult)):
            raise ConfigurationError(
                f"A2A skill '{skill.skill_id}' must return a mapping/dict or SkillResult"
            )
        await event_queue.enqueue_event(self._result_mapper.map(result))


    def _trace_incoming_request(self, message: object | None) -> None:
        """Trace an inbound A2A message without affecting request execution.

        Observability is deliberately fail-open.  Protocol inspection, protobuf
        conversion, A2UI summarization, and tracer sinks are diagnostic concerns;
        none may change the result of an otherwise valid A2A request.
        """

        if message is None:
            return
        try:
            message_document = MessageToDict(
                message, preserving_proto_field_name=True
            )
            fields: dict[str, object] = {
                "messageId": (
                    message_document.get("message_id")
                    or message_document.get("messageId")
                ),
                "contextId": (
                    message_document.get("context_id")
                    or message_document.get("contextId")
                ),
                "taskId": (
                    message_document.get("task_id")
                    or message_document.get("taskId")
                ),
            }
            metadata_document = message_document.get("metadata")
            if isinstance(metadata_document, Mapping):
                a2ui_metadata = summarize_a2ui_message_metadata(metadata_document)
                if a2ui_metadata is not None:
                    fields["a2uiMetadata"] = a2ui_metadata
            a2ui_parts = summarize_a2ui_parts(message_document)
            if a2ui_parts:
                fields["a2uiParts"] = a2ui_parts
            if self._protocol_tracer.include_payloads:
                fields["message"] = message_document
            self._protocol_tracer.emit(
                A2AProtocolTraceEvent("request.receive", "remote->server", fields)
            )
        except Exception:  # noqa: BLE001 - tracing must never break A2A execution.
            return

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Acknowledge cancellation for stateless business-handler execution."""

        del context, event_queue
