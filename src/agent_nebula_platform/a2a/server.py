"""Agent Nebula A2A integration.

This module contains only Nebula-specific functionality layered on a2a-sdk.
"""

from __future__ import annotations

from .config.server import A2AServerTlsConfiguration
from .security.server import A2ASecurityServerCallContextBuilder, A2AServerSecurityService

from dataclasses import dataclass
from urllib.parse import urlparse
from a2a.types import AgentCard, AgentInterface
from a2a.utils.constants import TransportProtocol
from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.plugins.base import RuntimePlugin
from pathlib import Path
from typing import Any
from a2a.server.request_handlers import RequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.routes.rest_routes import create_rest_routes
from a2a.types import AgentCard
from fastapi import FastAPI


@dataclass(frozen=True, slots=True)
class A2AHttpInterface:
    """Describe one HTTP-hosted A2A interface to mount on FastAPI."""
    binding: str
    path: str

@dataclass(frozen=True, slots=True)
class A2AGrpcInterface:
    """Describe one gRPC listener advertised by the Agent Card."""
    host: str
    port: int

    @property
    def address(self) -> str:
        """Return the grpcio listener address."""
        return f'{self.host}:{self.port}'

@dataclass(frozen=True, slots=True)
class A2AServerInterfacePlan:
    """Hold deduplicated runtime interfaces derived from an Agent Card."""
    http: tuple[A2AHttpInterface, ...]
    grpc: tuple[A2AGrpcInterface, ...]

class A2AServerInterfacePlanner:
    """Translate advertised A2A interfaces into concrete server bindings."""
    _HTTP_BINDINGS = frozenset({TransportProtocol.JSONRPC, TransportProtocol.HTTP_JSON})

    def plan(self, agent_card: AgentCard) -> A2AServerInterfacePlan:
        """Create a fail-closed transport plan from the published interfaces."""
        http: dict[tuple[str, str], A2AHttpInterface] = {}
        grpc: dict[tuple[str, int], A2AGrpcInterface] = {}
        for interface in agent_card.supported_interfaces:
            self._require_v1(interface)
            binding = interface.protocol_binding
            if binding in self._HTTP_BINDINGS:
                planned = A2AHttpInterface(binding=binding, path=self._http_path(interface))
                http[planned.binding, planned.path] = planned
            elif binding == TransportProtocol.GRPC:
                planned_grpc = self._grpc_interface(interface)
                grpc[planned_grpc.host, planned_grpc.port] = planned_grpc
            else:
                raise ConfigurationError('A2A Agent Card advertises an unsupported protocol binding', details={'protocol_binding': binding})
        return A2AServerInterfacePlan(http=tuple(http.values()), grpc=tuple(grpc.values()))

    @staticmethod
    def _require_v1(interface: AgentInterface) -> None:
        """Reject protocol versions outside the Runtime's A2A 1.0 contract."""
        if interface.protocol_version != '1.0':
            raise ConfigurationError('A2A Runtime supports protocol version 1.0 interfaces only', details={'protocol_binding': interface.protocol_binding, 'protocol_version': interface.protocol_version})

    @staticmethod
    def _http_path(interface: AgentInterface) -> str:
        """Extract the mounted path from one absolute HTTP(S) interface URL."""
        parsed = urlparse(interface.url)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            raise ConfigurationError('A2A HTTP interface must use an absolute HTTP(S) URL', details={'url': interface.url})
        return parsed.path or '/'

    @staticmethod
    def _grpc_interface(interface: AgentInterface) -> A2AGrpcInterface:
        """Resolve either an A2A authority or grpc:// URL into a listener."""
        value = interface.url.strip()
        parsed = urlparse(value if '://' in value else f'grpc://{value}')
        if parsed.scheme != 'grpc' or not parsed.hostname or parsed.port is None:
            raise ConfigurationError('A2A gRPC interface must identify a host and port', details={'url': interface.url})
        if parsed.path not in {'', '/'}:
            raise ConfigurationError('A2A gRPC interface must not contain an HTTP path', details={'url': interface.url})
        return A2AGrpcInterface(host=parsed.hostname, port=parsed.port)

class A2ASdkServerAdapter:
    """Expose only Agent Card interfaces implemented by official ``a2a-python``."""

    def __init__(self, *, app: FastAPI, agent_card: AgentCard, agent_card_route: str='/.well-known/agent-card.json', request_handler: RequestHandler, planner: A2AServerInterfacePlanner | None=None, security: A2AServerSecurityService | None=None, tls: A2AServerTlsConfiguration | None=None) -> None:
        """Store injected server dependencies without starting host infrastructure."""
        self._app = app
        self._agent_card = agent_card
        self._agent_card_route = agent_card_route
        self._request_handler = request_handler
        self._planner = planner or A2AServerInterfacePlanner()
        self._security = security
        self._tls = tls or A2AServerTlsConfiguration()
        self._grpc_servers: list[Any] = []
        self._plan: A2AServerInterfacePlan | None = None

    @property
    def plan(self) -> A2AServerInterfacePlan:
        """Return the validated interface plan after attachment."""
        if self._plan is None:
            raise ConfigurationError('A2A server interfaces have not been attached')
        return self._plan

    async def start(self) -> None:
        """Mount HTTP transports and start configured gRPC listeners."""
        if self._plan is not None:
            raise ConfigurationError('A2A server interfaces are already attached')
        plan = self._planner.plan(self._agent_card)
        if self._agent_card.security_requirements and self._security is None:
            raise ConfigurationError('A2A Agent Card advertises security but no server security service is configured')
        if self._security is not None:
            self._security.validate_configuration()
        self._attach_http(plan)
        await self._start_grpc(plan)
        self._plan = plan

    async def close(self) -> None:
        """Stop only gRPC listeners owned by this adapter."""
        for server in reversed(self._grpc_servers):
            await server.stop(grace=5.0)
        self._grpc_servers.clear()

    def _attach_http(self, plan: A2AServerInterfacePlan) -> None:
        """Mount official Agent Card, JSON-RPC, and HTTP+JSON routes."""
        context_builder = A2ASecurityServerCallContextBuilder(self._security) if self._security is not None else None
        jsonrpc_routes = []
        rest_routes = []
        for interface in plan.http:
            if interface.binding == TransportProtocol.JSONRPC:
                jsonrpc_routes.extend(create_jsonrpc_routes(request_handler=self._request_handler, rpc_url=interface.path, context_builder=context_builder))
            elif interface.binding == TransportProtocol.HTTP_JSON:
                rest_routes.extend(create_rest_routes(request_handler=self._request_handler, context_builder=context_builder, path_prefix=interface.path.rstrip('/')))
        self._app.router.routes.extend([*create_agent_card_routes(self._agent_card, card_url=self._agent_card_route), *jsonrpc_routes, *rest_routes])

    async def _start_grpc(self, plan: A2AServerInterfacePlan) -> None:
        """Start one official A2A gRPC service for each advertised listener."""
        if not plan.grpc:
            return
        try:
            import grpc
            from a2a.server.request_handlers import GrpcHandler
            from a2a.types import a2a_pb2_grpc
        except ImportError as exc:
            raise ConfigurationError("A2A gRPC interface requires the Platform 'a2a-grpc' extra") from exc
        if self._security is not None and self._security.required:
            raise ConfigurationError('Secured A2A gRPC interfaces require a gRPC security adapter; Platform will not expose them without one')
        for interface in plan.grpc:
            server = grpc.aio.server()
            a2a_pb2_grpc.add_A2AServiceServicer_to_server(GrpcHandler(self._request_handler), server)
            if self._tls.enabled:
                assert self._tls.certificate_file is not None
                assert self._tls.private_key_file is not None
                credentials = grpc.ssl_server_credentials(((self._read_tls_bytes(self._tls.private_key_file), self._read_tls_bytes(self._tls.certificate_file)),), root_certificates=self._read_tls_bytes(self._tls.trust_bundle) if self._tls.trust_bundle is not None else None, require_client_auth=self._tls.require_client_certificate)
                bound_port = server.add_secure_port(interface.address, credentials)
            else:
                bound_port = server.add_insecure_port(interface.address)
            if bound_port == 0:
                raise ConfigurationError('A2A gRPC listener could not bind its advertised interface', details={'address': interface.address})
            await server.start()
            self._grpc_servers.append(server)

    @staticmethod
    def _read_tls_bytes(path: Path) -> bytes:
        """Read configured gRPC TLS material and fail with configuration context."""
        try:
            return path.read_bytes()
        except OSError as exc:
            raise ConfigurationError('Unable to read A2A server TLS material', details={'path': str(path)}) from exc



class A2AServerPlugin(RuntimePlugin):
    """Attach native a2a-sdk server interfaces inside Platform Runtime lifecycle.

    This plugin intentionally lives in ``agent_nebula_platform.a2a``. Active
    Runtime composition must not depend on the deprecated ``protocols.a2a``
    implementation while examples are migrated to the official SDK.
    """

    def __init__(
        self,
        *,
        app: FastAPI,
        agent_card: AgentCard,
        agent_card_route: str = '/.well-known/agent-card.json',
        request_handler: RequestHandler,
        required: bool = True,
        security: A2AServerSecurityService | None = None,
        tls: A2AServerTlsConfiguration | None = None,
    ) -> None:
        self._app = app
        self._agent_card = agent_card
        self._agent_card_route = agent_card_route
        self._request_handler = request_handler
        self._required = required
        self._security = security
        self._tls = tls or A2AServerTlsConfiguration()

    @property
    def name(self) -> str:
        return 'a2a.server'

    @property
    def required(self) -> bool:
        return self._required

    async def initialize(self, context: RuntimeContext) -> None:
        """Start only interfaces advertised by the official Agent Card."""
        adapter = A2ASdkServerAdapter(
            app=self._app,
            agent_card=self._agent_card,
            agent_card_route=self._agent_card_route,
            request_handler=self._request_handler,
            security=self._security,
            tls=self._tls,
        )
        await adapter.start()
        context.services.register(self.name, adapter)

    async def close(self, context: RuntimeContext) -> None:
        """Stop Runtime-owned A2A listeners and unregister the adapter."""
        adapter = context.services.require(self.name, A2ASdkServerAdapter)
        await adapter.close()
        context.services.remove(self.name)
