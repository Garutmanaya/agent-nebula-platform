"""Official A2A 1.0 client construction owned by Agent Nebula Platform."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
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
    ) -> None:
        """Create one reusable client adapter from validated Platform configuration."""

        self._configuration = configuration
        self._security_interceptor = security_interceptor
        self._extension_context_builder = A2AClientExtensionContextBuilder(extensions)
        self._closed = False

    async def resolve_agent_card(self, base_url: str) -> AgentCard:
        """Resolve an official A2A 1.0 Agent Card from ``base_url``."""

        self._ensure_open()
        async with self._new_http_client() as client:
            resolver = A2ACardResolver(client, base_url)
            return await resolver.get_agent_card(
                relative_card_path=self._configuration.agent_card_path
            )

    async def resolve_agent_card_document(self, base_url: str) -> dict[str, Any]:
        """Resolve an Agent Card and return its protocol-neutral JSON representation.

        Higher-level facades use this operation so they do not need to import
        official A2A protobuf models or protobuf serialization utilities.
        """

        card = await self.resolve_agent_card(base_url)
        return MessageToDict(card, preserving_proto_field_name=True)

    async def connect(
        self,
        base_url: str,
        *,
        interceptors: list[ClientCallInterceptor] | None = None,
        skill_id: str | None = None,
    ) -> Client:
        """Resolve the remote card and create an official A2A client for it."""

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
        """Create an official client from an already resolved Agent Card."""

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
        client = self.create(card, skill_id=skill_id)
        responses: list[dict[str, Any]] = []
        try:
            async for response in client.send_message(
                request, context=extension_context.call_context
            ):
                responses.append(
                    MessageToDict(response, preserving_proto_field_name=True)
                )
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
        want_response: bool = False,
        action_id: str | None = None,
        context_id: str | None = None,
        task_id: str | None = None,
        skill_id: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        """Send one A2UI v1.0 renderer action over the standard A2A binding."""

        card = await self.resolve_agent_card(base_url)
        if not any(
            extension.uri == A2UI_EXTENSION_URI
            for extension in card.capabilities.extensions
        ):
            raise ConfigurationError("Remote A2A agent does not advertise A2UI v1.0")
        extension_context = self._extension_context_builder.build(card, skill_id=skill_id)
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
        client = self.create(card, skill_id=skill_id)
        responses: list[dict[str, Any]] = []
        try:
            async for response in client.send_message(
                request, context=extension_context.call_context
            ):
                responses.append(MessageToDict(response, preserving_proto_field_name=True))
        finally:
            await client.close()
        return tuple(responses)

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
