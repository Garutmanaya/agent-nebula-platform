"""Official ``a2a-python`` server transport integration for Agent Runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from a2a.server.request_handlers import RequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.routes.rest_routes import create_rest_routes
from a2a.types import AgentCard
from a2a.utils.constants import TransportProtocol
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route, request_response

from agent_nebula_platform.platform.errors import ConfigurationError

from .security import A2ASecurityRequest, A2AServerSecurityService
from .server_interfaces import A2AServerInterfacePlan, A2AServerInterfacePlanner


class A2AServerAdapter:
    """Expose only Agent Card interfaces implemented by official ``a2a-python``."""

    def __init__(
        self,
        *,
        app: FastAPI,
        agent_card: AgentCard,
        request_handler: RequestHandler,
        planner: A2AServerInterfacePlanner | None = None,
        security: A2AServerSecurityService | None = None,
    ) -> None:
        """Store injected server dependencies without starting host infrastructure."""

        self._app = app
        self._agent_card = agent_card
        self._request_handler = request_handler
        self._planner = planner or A2AServerInterfacePlanner()
        self._security = security
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

        jsonrpc_routes = []
        rest_routes = []
        for interface in plan.http:
            if interface.binding == TransportProtocol.JSONRPC:
                jsonrpc_routes.extend(
                    create_jsonrpc_routes(
                        request_handler=self._request_handler,
                        rpc_url=interface.path,
                    )
                )
            elif interface.binding == TransportProtocol.HTTP_JSON:
                rest_routes.extend(
                    create_rest_routes(
                        request_handler=self._request_handler,
                        path_prefix=interface.path.rstrip("/"),
                    )
                )
        # A2A SDK 1.0.x exposes Starlette route factories as the stable
        # server integration API.  Attach those routes directly to the
        # caller-owned FastAPI router instead of depending on the FastAPI
        # convenience helper introduced in a later SDK release.
        routes = [
            *create_agent_card_routes(self._agent_card),
            *jsonrpc_routes,
            *rest_routes,
        ]
        self._app.router.routes.extend(self._secure_http_routes(routes))

    def _secure_http_routes(self, routes: list[Any]) -> list[Any]:
        """Protect protocol routes while leaving public Agent Card discovery readable."""

        if self._security is None or not self._security.required:
            return routes
        secured: list[Any] = []
        for route in routes:
            if (
                isinstance(route, Route)
                and route.path == "/.well-known/agent-card.json"
            ):
                secured.append(route)
                continue
            if isinstance(route, Route):
                route.endpoint = self._secured_endpoint(route.endpoint)
                # Starlette creates the ASGI app from endpoint during Route construction.
                # Rebuild it after replacing the endpoint so enforcement cannot be bypassed.
                route.app = request_response(route.endpoint)
            elif isinstance(route, Mount):
                route.routes[:] = self._secure_http_routes(list(route.routes))
            secured.append(route)
        return secured

    def _secured_endpoint(
        self, endpoint: Callable[[Request], Awaitable[Response]]
    ) -> Callable[[Request], Awaitable[Response]]:
        """Wrap one official HTTP endpoint with Agent Card security enforcement."""

        async def secured(request: Request) -> Response:
            assert self._security is not None
            try:
                principals = self._security.authenticate(
                    A2ASecurityRequest(
                        headers={
                            key.lower(): value for key, value in request.headers.items()
                        },
                        http_method=request.method,
                        target_uri=str(request.url),
                    )
                )
            except (
                Exception
            ) as exc:  # Authentication implementations fail closed at HTTP boundary.
                from agent_nebula_platform.platform.errors import AuthenticationError

                if not isinstance(exc, AuthenticationError):
                    raise
                return JSONResponse(
                    {"error": "unauthorized", "message": str(exc)}, status_code=401
                )
            request.scope["a2a.security"] = principals
            return await endpoint(request)

        return secured

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
                "A2A gRPC interface requires the Runtime 'a2a-grpc' extra"
            ) from exc

        if self._security is not None and self._security.required:
            raise ConfigurationError(
                "Secured A2A gRPC interfaces require a gRPC security adapter; "
                "Runtime will not expose them without one"
            )

        for interface in plan.grpc:
            server = grpc.aio.server()
            a2a_pb2_grpc.add_A2AServiceServicer_to_server(
                GrpcHandler(self._request_handler), server
            )
            bound_port = server.add_insecure_port(interface.address)
            if bound_port == 0:
                raise ConfigurationError(
                    "A2A gRPC listener could not bind its advertised interface",
                    details={"address": interface.address},
                )
            await server.start()
            self._grpc_servers.append(server)
