"""Official ``a2a-python`` server transport integration for Agent Runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from a2a.server.request_handlers import RequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.routes.rest_routes import create_rest_routes
from a2a.types import AgentCard
from a2a.utils.constants import TransportProtocol
from fastapi import FastAPI

from agent_nebula_platform.platform.errors import ConfigurationError

from ..security.context import A2ASecurityServerCallContextBuilder
from ..security.security import A2AServerSecurityService
from .configuration.listener import A2AServerTlsConfiguration
from .server_interfaces import A2AServerInterfacePlan, A2AServerInterfacePlanner


class A2ASdkServerAdapter:
    """Expose only Agent Card interfaces implemented by official ``a2a-python``."""

    def __init__(
        self,
        *,
        app: FastAPI,
        agent_card: AgentCard,
        agent_card_route: str = "/.well-known/agent-card.json",
        request_handler: RequestHandler,
        planner: A2AServerInterfacePlanner | None = None,
        security: A2AServerSecurityService | None = None,
        tls: A2AServerTlsConfiguration | None = None,
    ) -> None:
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
            raise ConfigurationError("A2A server interfaces have not been attached")
        return self._plan

    async def start(self) -> None:
        """Mount HTTP transports and start configured gRPC listeners."""

        if self._plan is not None:
            raise ConfigurationError("A2A server interfaces are already attached")
        plan = self._planner.plan(self._agent_card)
        if self._agent_card.security_requirements and self._security is None:
            raise ConfigurationError(
                "A2A Agent Card advertises security but no server security service is configured"
            )
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

        # AGENT NEBULA SECURITY: authenticate through the official a2a-sdk
        # ServerCallContextBuilder extension point instead of wrapping or replacing
        # SDK-generated protocol routes. Agent Card discovery remains public because
        # the context builder is supplied only to A2A protocol route factories.
        context_builder = (
            A2ASecurityServerCallContextBuilder(self._security)
            if self._security is not None
            else None
        )
        jsonrpc_routes = []
        rest_routes = []
        for interface in plan.http:
            if interface.binding == TransportProtocol.JSONRPC:
                jsonrpc_routes.extend(
                    create_jsonrpc_routes(
                        request_handler=self._request_handler,
                        rpc_url=interface.path,
                        context_builder=context_builder,
                    )
                )
            elif interface.binding == TransportProtocol.HTTP_JSON:
                rest_routes.extend(
                    create_rest_routes(
                        request_handler=self._request_handler,
                        context_builder=context_builder,
                        path_prefix=interface.path.rstrip("/"),
                    )
                )
        # A2A SDK 1.0.x exposes Starlette route factories as the stable
        # server integration API.  Attach those routes directly to the
        # caller-owned FastAPI router instead of depending on the FastAPI
        # convenience helper introduced in a later SDK release.
        self._app.router.routes.extend(
            [
                *create_agent_card_routes(
                    self._agent_card, card_url=self._agent_card_route
                ),
                *jsonrpc_routes,
                *rest_routes,
            ]
        )

    async def _start_grpc(self, plan: A2AServerInterfacePlan) -> None:
        """Start one official A2A gRPC service for each advertised listener."""

        if not plan.grpc:
            return
        try:
            import grpc
            from a2a.server.request_handlers import GrpcHandler
            from a2a.types import a2a_pb2_grpc
        except ImportError as exc:
            raise ConfigurationError(
                "A2A gRPC interface requires the Platform 'a2a-grpc' extra"
            ) from exc

        if self._security is not None and self._security.required:
            raise ConfigurationError(
                "Secured A2A gRPC interfaces require a gRPC security adapter; "
                "Platform will not expose them without one"
            )

        for interface in plan.grpc:
            server = grpc.aio.server()
            a2a_pb2_grpc.add_A2AServiceServicer_to_server(
                GrpcHandler(self._request_handler), server
            )
            if self._tls.enabled:
                assert self._tls.certificate_file is not None
                assert self._tls.private_key_file is not None
                credentials = grpc.ssl_server_credentials(
                    ((
                        self._read_tls_bytes(self._tls.private_key_file),
                        self._read_tls_bytes(self._tls.certificate_file),
                    ),),
                    root_certificates=(
                        self._read_tls_bytes(self._tls.trust_bundle)
                        if self._tls.trust_bundle is not None
                        else None
                    ),
                    require_client_auth=self._tls.require_client_certificate,
                )
                bound_port = server.add_secure_port(interface.address, credentials)
            else:
                bound_port = server.add_insecure_port(interface.address)
            if bound_port == 0:
                raise ConfigurationError(
                    "A2A gRPC listener could not bind its advertised interface",
                    details={"address": interface.address},
                )
            await server.start()
            self._grpc_servers.append(server)

    @staticmethod
    def _read_tls_bytes(path: Path) -> bytes:
        """Read configured gRPC TLS material and fail with configuration context."""

        try:
            return path.read_bytes()
        except OSError as exc:
            raise ConfigurationError(
                "Unable to read A2A server TLS material", details={"path": str(path)}
            ) from exc
