"""Official A2A 1.0 client construction owned by Agent Nebula Platform."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, Client, ClientConfig, ClientFactory
from a2a.types import AgentCard, Message, Part, Role, SendMessageRequest
from a2a.utils.constants import TransportProtocol
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct, Value

from agent_nebula_platform.a2ui.models import A2UIActionRequest, A2UI_STABLE_VERSION
from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.protocols.a2a.extensions.a2ui.extension import A2UI_EXTENSION_URI
from agent_nebula_platform.protocols.a2a.extensions.a2ui.parts import create_a2ui_action_part
from agent_nebula_platform.protocols.a2a.extensions import require_supported_skill
from agent_nebula_platform.protocols.a2a.extensions.a2ui.observability import (
    summarize_a2ui_agent_card,
    summarize_a2ui_message_metadata,
    summarize_a2ui_parts,
)
from agent_nebula_platform.protocols.a2a.observability import (
    A2AProtocolTraceEvent,
    A2AProtocolTracer,
)
from agent_nebula_platform.protocols.a2a.observability.tracer import (
    create_protocol_tracer_from_environment,
)
from agent_nebula_platform.platform.tls import FileTlsContextProvider

from .client_configuration import A2AClientConfiguration
from .extension_context import A2AClientExtension, A2AClientExtensionContextBuilder
from .client_security import A2AClientSecurityInterceptor

if TYPE_CHECKING:
    from a2a.client.interceptors import ClientCallInterceptor


class A2AClientAdapter:
    """Resolve standard Agent Cards and construct official transport clients.

    Security negotiation is supplied through a Platform interceptor that evaluates
    the remote Agent Card without modifying official A2A protocol models.
    """

    def __init__(
        self,
        configuration: A2AClientConfiguration,
        *,
        security_interceptor: A2AClientSecurityInterceptor | None = None,
        extensions: tuple[A2AClientExtension, ...] = (),
        protocol_tracer: A2AProtocolTracer | None = None,
    ) -> None:
        """Create one reusable client adapter from validated Platform configuration."""

        self._configuration = configuration
        self._security_interceptor = security_interceptor
        self._extension_context_builder = A2AClientExtensionContextBuilder(extensions)
        self._protocol_tracer = protocol_tracer or create_protocol_tracer_from_environment()
        self._closed = False

    async def resolve_agent_card(self, location: str) -> AgentCard:
        """Resolve the authoritative A2A 1.0 Agent Card from a discovery location.

        ``location`` may be either an agent base URL or the explicit Agent Card
        URL returned by an optional registry. Registry data is used only to locate
        the card; all invocation and security facts are read from the resolved card.
        """

        self._ensure_open()
        base_url, card_path = self._agent_card_resolution_target(location)
        async with self._new_http_client() as client:
            resolver = A2ACardResolver(client, base_url)
            card = await resolver.get_agent_card(relative_card_path=card_path)
        self._trace_resolved_agent_card(card, location=location)
        return card

    def _agent_card_resolution_target(self, location: str) -> tuple[str, str]:
        """Normalize a base URL or explicit Agent Card URL for ``A2ACardResolver``."""

        configured_path = self._configuration.agent_card_path or "/.well-known/agent-card.json"
        parsed = urlsplit(location)
        if parsed.path.endswith(configured_path):
            base_path = parsed.path[: -len(configured_path)].rstrip("/")
            base_url = urlunsplit((parsed.scheme, parsed.netloc, base_path, "", ""))
            return base_url, configured_path
        return location, configured_path

    async def connect(
        self,
        base_url: str,
        *,
        interceptors: list[ClientCallInterceptor] | None = None,
        skill_id: str | None = None,
    ) -> Client:
        """Resolve the remote card and return an official ``a2a-sdk`` client.

        AGENT NEBULA INTEGRATION:
        Platform supplies external configuration, TLS, security interceptors and
        optional Nebula extension context. It does not wrap standard Client
        operations; callers use the returned SDK client directly.
        """

        card = await self.resolve_agent_card(base_url)
        if skill_id is not None:
            require_supported_skill(card, skill_id)
        return self.create(card, interceptors=interceptors, skill_id=skill_id)

    def create(
        self,
        agent_card: AgentCard,
        *,
        interceptors: list[ClientCallInterceptor] | None = None,
        skill_id: str | None = None,
    ) -> Client:
        """Create and return an official client from a resolved Agent Card.

        AGENT NEBULA INTEGRATION:
        The only additions here are configuration and interceptors installed via
        official ``a2a-sdk`` extension points. The returned object is the SDK's
        native ``Client``.
        """

        self._ensure_open()
        config = ClientConfig(
            streaming=self._configuration.streaming,
            polling=self._configuration.polling,
            # Official HTTP transports own and close this client with the A2A Client.
            httpx_client=self._new_http_client(
                agent_card=agent_card, skill_id=skill_id
            ),
            grpc_channel_factory=self._grpc_channel_factory(),
            supported_protocol_bindings=list(
                self._configuration.supported_protocol_bindings
            ),
            use_client_preference=self._configuration.use_client_preference,
            accepted_output_modes=list(self._configuration.accepted_output_modes),
        )
        try:
            effective_interceptors = list(interceptors or [])
            if self._security_interceptor is not None:
                effective_interceptors.insert(0, self._security_interceptor)
            return ClientFactory(config).create(agent_card, effective_interceptors)
        except (ImportError, ValueError) as exc:
            raise ConfigurationError(
                "A2A client cannot select a compatible configured transport",
                details={
                    "supported_protocol_bindings": list(
                        self._configuration.supported_protocol_bindings
                    )
                },
            ) from exc

    async def send_message(
        self,
        base_url: str,
        *,
        text: str | None = None,
        data: Mapping[str, Any] | None = None,
        context_id: str | None = None,
        task_id: str | None = None,
        skill_id: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        """Send one official A2A ``SendMessageRequest`` and normalize responses.

        Platform owns protobuf construction so higher-level facades do not depend
        on A2A wire models. When ``skill_id`` is supplied, Platform uses the formal
        Agent Nebula A2A skill-selection extension rather than changing any core
        A2A model. The client remains responsible for selecting the skill.
        """

        if text is None and data is None:
            raise ConfigurationError(
                "A2A message requires text, structured data, or both"
            )
        parts: list[Part] = []
        if text is not None:
            normalized = text.strip()
            if not normalized:
                raise ConfigurationError("A2A message text must not be blank")
            parts.append(Part(text=normalized))
        if data is not None:
            parts.append(Part(data=ParseDict(dict(data), Value())))
        card = await self.resolve_agent_card(base_url)
        extension_context = self._extension_context_builder.build(
            card, skill_id=skill_id
        )
        message_arguments: dict[str, Any] = {
            "message_id": str(uuid4()),
            "context_id": context_id or "",
            "task_id": task_id or "",
            "role": Role.ROLE_USER,
            "parts": parts,
        }
        if extension_context.message_metadata is not None:
            message_arguments["metadata"] = extension_context.message_metadata
        request_arguments: dict[str, Any] = {
            "message": Message(**message_arguments)
        }
        if extension_context.request_metadata is not None:
            request_arguments["metadata"] = extension_context.request_metadata
        request = SendMessageRequest(**request_arguments)
        request_document = MessageToDict(request, preserving_proto_field_name=True)
        self._trace_outgoing_request(
            request_document,
            card=card,
            skill_id=skill_id,
            operation="SendMessage",
        )
        client = self.create(card, skill_id=skill_id)
        responses: list[dict[str, Any]] = []
        try:
            async for response in client.send_message(
                request, context=extension_context.call_context
            ):
                response_document = MessageToDict(
                    response, preserving_proto_field_name=True
                )
                responses.append(response_document)
                self._trace_incoming_response(response_document)
        finally:
            await client.close()
        return tuple(responses)

    async def send_a2ui_action(
        self,
        base_url: str,
        *,
        name: str,
        surface_id: str,
        source_component_id: str,
        context: Mapping[str, Any] | None = None,
        data_model: Mapping[str, Any] | None = None,
        context_id: str | None = None,
        task_id: str | None = None,
        want_response: bool = False,
        action_id: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        """Send one A2UI v1.0 renderer action over the standard A2A binding."""

        card = await self.resolve_agent_card(base_url)
        if not any(
            extension.uri == A2UI_EXTENSION_URI
            for extension in card.capabilities.extensions
        ):
            raise ConfigurationError("Remote A2A agent does not advertise A2UI v1.0")
        extension_context = self._extension_context_builder.build(card)
        action = A2UIActionRequest(
            version=A2UI_STABLE_VERSION,
            name=name,
            surface_id=surface_id,
            source_component_id=source_component_id,
            timestamp=datetime.now(timezone.utc),
            context=dict(context or {}),
            want_response=want_response,
            action_id=action_id,
        )
        message_metadata = (
            MessageToDict(extension_context.message_metadata, preserving_proto_field_name=True)
            if extension_context.message_metadata is not None
            else {}
        )
        if data_model is not None:
            message_metadata["a2uiRendererDataModel"] = {
                "version": A2UI_STABLE_VERSION,
                "surfaces": {surface_id: dict(data_model)},
            }
        message_arguments: dict[str, Any] = {
            "message_id": str(uuid4()),
            "context_id": context_id or "",
            "task_id": task_id or "",
            "role": Role.ROLE_USER,
            "parts": [create_a2ui_action_part(action)],
            "extensions": [A2UI_EXTENSION_URI],
        }
        if message_metadata:
            message_arguments["metadata"] = ParseDict(message_metadata, Struct())
        request_arguments: dict[str, Any] = {"message": Message(**message_arguments)}
        if extension_context.request_metadata is not None:
            request_arguments["metadata"] = extension_context.request_metadata
        request = SendMessageRequest(**request_arguments)
        request_document = MessageToDict(request, preserving_proto_field_name=True)
        self._trace_outgoing_request(
            request_document,
            card=card,
            skill_id=None,
            operation="SendMessage",
        )
        client = self.create(card)
        responses: list[dict[str, Any]] = []
        try:
            async for response in client.send_message(
                request, context=extension_context.call_context
            ):
                response_document = MessageToDict(
                    response, preserving_proto_field_name=True
                )
                responses.append(response_document)
                self._trace_incoming_response(response_document)
        finally:
            await client.close()
        return tuple(responses)


    def _trace_resolved_agent_card(self, card: AgentCard, *, location: str) -> None:
        """Trace Agent Card discovery without affecting successful discovery."""

        try:
            card_document = MessageToDict(card, preserving_proto_field_name=True)
            fields: dict[str, Any] = {
                "location": location,
                "name": card.name,
                "interfaces": card_document.get("supportedInterfaces", []),
            }
            a2ui = summarize_a2ui_agent_card(card_document)
            if a2ui is not None:
                fields["a2ui"] = a2ui
            if self._protocol_tracer.include_payloads:
                fields["agentCard"] = card_document
            self._protocol_tracer.emit(
                A2AProtocolTraceEvent(
                    "agent_card.resolved", "remote->client", fields
                )
            )
        except Exception:  # noqa: BLE001 - tracing must never break A2A discovery.
            return

    def _trace_outgoing_request(
        self,
        request: dict[str, Any],
        *,
        card: AgentCard,
        skill_id: str | None,
        operation: str,
    ) -> None:
        """Trace an outbound A2A request without affecting request delivery."""

        try:
            message = request.get("message") if isinstance(request, dict) else None
            metadata = message.get("metadata", {}) if isinstance(message, dict) else {}
            fields: dict[str, Any] = {
                "operation": operation,
                "agent": card.name,
                "skillId": skill_id,
                "messageId": (
                    message.get("message_id") or message.get("messageId")
                )
                if isinstance(message, dict)
                else None,
                "contextId": (
                    message.get("context_id") or message.get("contextId")
                )
                if isinstance(message, dict)
                else None,
                "taskId": (message.get("task_id") or message.get("taskId"))
                if isinstance(message, dict)
                else None,
            }
            if isinstance(metadata, Mapping):
                a2ui_metadata = summarize_a2ui_message_metadata(metadata)
                if a2ui_metadata is not None:
                    fields["a2uiMetadata"] = a2ui_metadata
            a2ui_parts = summarize_a2ui_parts(request)
            if a2ui_parts:
                fields["a2uiParts"] = a2ui_parts
            if self._protocol_tracer.include_payloads:
                fields["request"] = request
            self._protocol_tracer.emit(
                A2AProtocolTraceEvent("request.send", "client->remote", fields)
            )
        except Exception:  # noqa: BLE001 - tracing must never break A2A delivery.
            return

    def _trace_incoming_response(self, response: dict[str, Any]) -> None:
        """Trace an inbound A2A response without affecting response handling."""

        try:
            fields: dict[str, Any] = {}
            a2ui_parts = summarize_a2ui_parts(response)
            if a2ui_parts:
                fields["a2uiParts"] = a2ui_parts
            if self._protocol_tracer.include_payloads:
                fields["response"] = response
            self._protocol_tracer.emit(
                A2AProtocolTraceEvent("response.receive", "remote->client", fields)
            )
        except Exception:  # noqa: BLE001 - tracing must never break response handling.
            return

    async def close(self) -> None:
        """Close Platform-owned transport resources idempotently."""

        if self._closed:
            return
        self._closed = True
        if self._security_interceptor is not None:
            await self._security_interceptor.close()

    def _new_http_client(
        self, *, agent_card: AgentCard | None = None, skill_id: str | None = None
    ) -> httpx.AsyncClient:
        self._ensure_open()
        tls = self._configuration.tls
        context: bool | object
        # HTTPX selects TLS from the remote URL.  ``enabled`` controls explicit
        # client TLS/mTLS material; a configured trust bundle must still verify
        # ordinary HTTPS when mTLS is disabled.  Never translate disabled mTLS
        # into ``verify=False`` because that silently disables server identity
        # verification for Agent Card and A2A HTTPS requests.
        if tls.trust_bundle is not None:
            context = FileTlsContextProvider(
                ca_file=tls.trust_bundle,
                certificate_file=tls.certificate_file if tls.enabled else None,
                private_key_file=tls.private_key_file if tls.enabled else None,
            ).create_client_context()
        else:
            import ssl

            context = ssl.create_default_context()
            if tls.enabled and tls.certificate_file is not None:
                context.load_cert_chain(
                    str(tls.certificate_file), str(tls.private_key_file)
                )
        event_hooks = None
        if agent_card is not None and self._security_interceptor is not None:

            async def apply_request_security(request: httpx.Request) -> None:
                """Bind request-sensitive credentials after the final HTTP URI is known."""

                await self._security_interceptor.apply_http_request_security(
                    agent_card=agent_card,
                    http_method=request.method,
                    target_uri=str(request.url),
                    headers=request.headers,
                    skill_id=skill_id,
                )

            event_hooks = {"request": [apply_request_security]}

        return httpx.AsyncClient(
            verify=context,
            timeout=httpx.Timeout(self._configuration.timeout_seconds),
            event_hooks=event_hooks,
        )

    def _grpc_channel_factory(self) -> Callable[[str], object] | None:
        if (
            TransportProtocol.GRPC
            not in self._configuration.supported_protocol_bindings
        ):
            return None
        try:
            import grpc
        except ImportError as exc:
            raise ConfigurationError(
                'A2A gRPC client support requires the Platform "a2a-grpc" extra'
            ) from exc

        tls = self._configuration.tls
        if not tls.enabled:

            def create_insecure_channel(target: str) -> object:
                """Create a plaintext gRPC channel when transport TLS is disabled."""

                authority = target.removeprefix("grpc://").removeprefix("grpcs://")
                return grpc.aio.insecure_channel(authority)

            return create_insecure_channel

        root_certificates = (
            self._read_bytes(tls.trust_bundle) if tls.trust_bundle is not None else None
        )
        private_key = (
            self._read_bytes(tls.private_key_file) if tls.private_key_file else None
        )
        certificate_chain = (
            self._read_bytes(tls.certificate_file) if tls.certificate_file else None
        )
        credentials = grpc.ssl_channel_credentials(
            root_certificates=root_certificates,
            private_key=private_key,
            certificate_chain=certificate_chain,
        )

        def create_secure_channel(target: str) -> object:
            """Create a peer-verifying TLS gRPC channel for the selected interface."""

            authority = target.removeprefix("grpcs://").removeprefix("grpc://")
            return grpc.aio.secure_channel(authority, credentials)

        return create_secure_channel

    @staticmethod
    def _read_bytes(path: Path) -> bytes:
        try:
            return path.read_bytes()
        except OSError as exc:
            raise ConfigurationError(
                "Unable to read A2A client TLS material", details={"path": str(path)}
            ) from exc

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("A2A client adapter is closed")
