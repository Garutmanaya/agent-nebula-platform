"""Native ``a2a-sdk`` multi-skill execution for Agent Nebula.

This module intentionally keeps Agent Nebula at the dispatch boundary.  A
selected application skill is a normal ``a2a-sdk`` ``AgentExecutor`` and
receives the original ``RequestContext`` and ``EventQueue`` unchanged.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from google.protobuf.json_format import MessageToDict

from agent_nebula_platform.a2ui.models import A2UIActionRequest
from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.protocols.a2a.extensions import selected_skill_id
from agent_nebula_platform.protocols.a2a.extensions.a2ui.observability import (
    summarize_a2ui_message_metadata,
    summarize_a2ui_parts,
)
from agent_nebula_platform.protocols.a2a.extensions.a2ui.parts import (
    parse_a2ui_action_part,
)
from agent_nebula_platform.protocols.a2a.observability import (
    A2AProtocolTraceEvent,
    A2AProtocolTracer,
)
from agent_nebula_platform.protocols.a2a.observability.tracer import (
    create_protocol_tracer_from_environment,
)
from agent_nebula_platform.skills import SkillResult

# Existing A2UI action contract is deliberately preserved during the experiment.
# It is isolated from normal native A2A skill execution.
type A2UIBusinessResult = Mapping[str, object] | SkillResult
type A2UIActionHandler = Callable[
    [A2UIActionRequest, Mapping[str, object]],
    A2UIBusinessResult | Awaitable[A2UIBusinessResult],
]


class A2ASdkExecutableSkill(Protocol):
    """Application skill backed by a native ``a2a-sdk`` executor."""

    @property
    def skill_id(self) -> str: ...

    @property
    def executor(self) -> AgentExecutor: ...

    @property
    def schema_contract_id(self) -> str | None: ...

    @property
    def input_schema(self) -> Mapping[str, Any] | None: ...

    @property
    def output_schema(self) -> Mapping[str, Any] | None: ...


class A2ASdkAgentExecutor(AgentExecutor):
    """Dispatch a request to a selected native ``a2a-sdk`` skill executor.

    Agent Nebula owns only deterministic skill selection.  The selected
    application executor owns standard A2A execution and publishes Message,
    Task, status, and artifact events directly to the SDK EventQueue.
    """

    def __init__(
        self,
        skills: tuple[A2ASdkExecutableSkill, ...],
        *,
        protocol_tracer: A2AProtocolTracer | None = None,
        a2ui_action_handler: A2UIActionHandler | None = None,
    ) -> None:
        if not skills:
            raise ConfigurationError("A2A server requires at least one executable skill")
        self._skills = {skill.skill_id: skill for skill in skills}
        if len(self._skills) != len(skills):
            raise ConfigurationError("A2A executable skill identifiers must be unique")
        self._protocol_tracer = protocol_tracer or create_protocol_tracer_from_environment()
        self._a2ui_action_handler = a2ui_action_handler
        # Cancellation requests do not carry SendMessage extension metadata.
        # Remember the executor selected for each SDK-generated task id.
        self._task_skills: dict[str, str] = {}

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        self._trace_incoming_request(context.message)

        a2ui_action, payload = self._parse_a2ui_action(context)
        if a2ui_action is not None:
            await self._execute_a2ui_action(a2ui_action, payload, event_queue)
            return

        skill = self._select_skill(context)
        if context.task_id is not None:
            self._task_skills[context.task_id] = skill.skill_id

        # STANDARD A2A: do not adapt context, queue, or application result.
        await skill.executor.execute(context, event_queue)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        skill = self._skill_for_cancel(context)
        try:
            await skill.executor.cancel(context, event_queue)
        finally:
            if context.task_id is not None:
                self._task_skills.pop(context.task_id, None)

    def _select_skill(self, context: RequestContext) -> A2ASdkExecutableSkill:
        skill_id = selected_skill_id(
            metadata=context.metadata,
            requested_extensions=context.requested_extensions,
        )
        if skill_id is None:
            if len(self._skills) != 1:
                raise ConfigurationError(
                    "Multi-skill A2A agent requires the Nebula skill-selection extension"
                )
            return next(iter(self._skills.values()))
        skill = self._skills.get(skill_id)
        if skill is None:
            raise ConfigurationError(f"Selected A2A skill is not registered: {skill_id}")
        return skill

    def _skill_for_cancel(self, context: RequestContext) -> A2ASdkExecutableSkill:
        if context.task_id is not None:
            skill_id = self._task_skills.get(context.task_id)
            if skill_id is not None:
                return self._skills[skill_id]
        if len(self._skills) == 1:
            return next(iter(self._skills.values()))
        raise ConfigurationError(
            "Cannot route cancellation for a multi-skill task without its selected skill"
        )

    def _parse_a2ui_action(
        self, context: RequestContext
    ) -> tuple[A2UIActionRequest | None, dict[str, object]]:
        """Preserve current A2UI renderer-action dispatch independently of skills."""

        message = context.message
        payload: dict[str, object] = {}
        if message is None:
            return None, payload

        action: A2UIActionRequest | None = None
        for part in message.parts:
            parsed = parse_a2ui_action_part(part)
            if parsed is not None:
                if action is not None:
                    raise ConfigurationError("A2A message may contain only one A2UI action")
                action = parsed
                continue
            if part.HasField("data"):
                data = MessageToDict(part.data)
                if isinstance(data, dict):
                    payload.update(data)

        if action is not None and message.HasField("metadata"):
            metadata = MessageToDict(message.metadata)
            renderer_model = metadata.get("a2uiRendererDataModel")
            if isinstance(renderer_model, dict):
                payload["a2ui_renderer_data_model"] = renderer_model
        return action, payload

    async def _execute_a2ui_action(
        self,
        action: A2UIActionRequest,
        payload: Mapping[str, object],
        event_queue: EventQueue,
    ) -> None:
        """Keep existing A2UI action behavior isolated from native skill execution."""

        if self._a2ui_action_handler is None:
            raise ConfigurationError(
                "A2UI renderer action received but no A2UI action handler is configured"
            )
        # Compatibility boundary only: existing A2UI handlers still return the
        # current protocol-neutral result while Example 15 validates native A2A
        # skill execution independently.
        from agent_nebula_platform.protocols.a2a.server.result_mapper import A2AResultMapper

        result = self._a2ui_action_handler(action, payload)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, (Mapping, SkillResult)):
            raise ConfigurationError(
                "A2UI action handler must return a mapping/dict or SkillResult"
            )
        await event_queue.enqueue_event(
            A2AResultMapper(protocol_tracer=self._protocol_tracer).map(result)
        )

    def _trace_incoming_request(self, message: object | None) -> None:
        if message is None:
            return
        try:
            document = MessageToDict(message, preserving_proto_field_name=True)
            fields: dict[str, object] = {
                "messageId": document.get("message_id") or document.get("messageId"),
                "contextId": document.get("context_id") or document.get("contextId"),
                "taskId": document.get("task_id") or document.get("taskId"),
            }
            metadata = document.get("metadata")
            if isinstance(metadata, Mapping):
                a2ui_metadata = summarize_a2ui_message_metadata(metadata)
                if a2ui_metadata is not None:
                    fields["a2uiMetadata"] = a2ui_metadata
            a2ui_parts = summarize_a2ui_parts(document)
            if a2ui_parts:
                fields["a2uiParts"] = a2ui_parts
            if self._protocol_tracer.include_payloads:
                fields["message"] = document
            self._protocol_tracer.emit(
                A2AProtocolTraceEvent("request.receive", "remote->server", fields)
            )
        except Exception:  # noqa: BLE001 - observability must remain fail-open.
            return
