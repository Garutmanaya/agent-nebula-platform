"""Pre-execution AgentSkill authorization for native a2a-sdk request handling."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from google.protobuf.json_format import MessageToDict

from a2a.server.context import ServerCallContext
from a2a.server.events import Event
from a2a.server.request_handlers import RequestHandler
from a2a.types import (
    AgentCard,
    CancelTaskRequest,
    DeleteTaskPushNotificationConfigRequest,
    GetExtendedAgentCardRequest,
    GetTaskPushNotificationConfigRequest,
    GetTaskRequest,
    ListTaskPushNotificationConfigsRequest,
    ListTaskPushNotificationConfigsResponse,
    ListTasksRequest,
    ListTasksResponse,
    Message,
    SendMessageRequest,
    SubscribeToTaskRequest,
    Task,
    TaskPushNotificationConfig,
)

from agent_nebula_platform.a2a.extensions import selected_skill_id
from agent_nebula_platform.platform.errors import AuthenticationError

from .server import A2AServerSecurityService


class A2AAuthorizedRequestHandler(RequestHandler):
    """Authorize a selected AgentSkill before delegating to a2a-sdk execution.

    NEBULA A2A SECURITY:
    ``a2a-sdk`` deliberately exposes ``RequestHandler`` as the common request
    boundary for JSON-RPC, HTTP+JSON, and gRPC.  At this point the transport has
    already parsed ``SendMessageRequest`` and supplied ``ServerCallContext``, but
    ``DefaultRequestHandler`` has not invoked ``AgentExecutor`` yet.

    Agent Nebula therefore enforces skill-level ``securityRequirements`` here.
    The wrapper does not parse transport payloads and does not implement A2A
    execution; all authorized requests are delegated unchanged to the native SDK
    handler.
    """

    def __init__(
        self,
        *,
        inner: RequestHandler,
        agent_card: AgentCard,
        security: A2AServerSecurityService,
    ) -> None:
        self._inner = inner
        self._agent_card = agent_card
        self._security = security

    def _authorize_send(
        self,
        params: SendMessageRequest,
        context: ServerCallContext,
    ) -> None:
        metadata = MessageToDict(params.metadata) if params.HasField("metadata") else {}
        skill_id = selected_skill_id(
            metadata=metadata,
            requested_extensions=context.requested_extensions,
        )
        if skill_id is None:
            if len(self._agent_card.skills) != 1:
                raise AuthenticationError(
                    "Multi-skill A2A agent requires the Nebula skill-selection extension"
                )
            skill_id = self._agent_card.skills[0].id
        self._security.authorize_skill(skill_id=skill_id, call_context=context)

    async def on_message_send(
        self, params: SendMessageRequest, context: ServerCallContext
    ) -> Task | Message:
        self._authorize_send(params, context)
        return await self._inner.on_message_send(params, context)

    async def on_message_send_stream(
        self, params: SendMessageRequest, context: ServerCallContext
    ) -> AsyncGenerator[Event]:
        self._authorize_send(params, context)
        async for event in self._inner.on_message_send_stream(params, context):
            yield event

    async def on_get_task(self, params: GetTaskRequest, context: ServerCallContext) -> Task | None:
        return await self._inner.on_get_task(params, context)

    async def on_list_tasks(self, params: ListTasksRequest, context: ServerCallContext) -> ListTasksResponse:
        return await self._inner.on_list_tasks(params, context)

    async def on_cancel_task(self, params: CancelTaskRequest, context: ServerCallContext) -> Task | None:
        return await self._inner.on_cancel_task(params, context)

    async def on_create_task_push_notification_config(self, params: TaskPushNotificationConfig, context: ServerCallContext) -> TaskPushNotificationConfig:
        return await self._inner.on_create_task_push_notification_config(params, context)

    async def on_get_task_push_notification_config(self, params: GetTaskPushNotificationConfigRequest, context: ServerCallContext) -> TaskPushNotificationConfig:
        return await self._inner.on_get_task_push_notification_config(params, context)

    async def on_subscribe_to_task(self, params: SubscribeToTaskRequest, context: ServerCallContext) -> AsyncGenerator[Event]:
        async for event in self._inner.on_subscribe_to_task(params, context):
            yield event

    async def on_list_task_push_notification_configs(self, params: ListTaskPushNotificationConfigsRequest, context: ServerCallContext) -> ListTaskPushNotificationConfigsResponse:
        return await self._inner.on_list_task_push_notification_configs(params, context)

    async def on_delete_task_push_notification_config(self, params: DeleteTaskPushNotificationConfigRequest, context: ServerCallContext) -> None:
        await self._inner.on_delete_task_push_notification_config(params, context)

    async def on_get_extended_agent_card(self, params: GetExtendedAgentCardRequest, context: ServerCallContext) -> AgentCard:
        return await self._inner.on_get_extended_agent_card(params, context)
