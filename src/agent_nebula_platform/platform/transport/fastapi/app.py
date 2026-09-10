"""FastAPI integration for opt-in Agent Runtime capabilities.

The adapter attaches non-A2A routes to a caller-owned application and never
starts a server, mutates global logging, or replaces the host lifespan. Official
A2A 1.0 routes are owned exclusively by ``A2AServerAdapter``.
"""

from __future__ import annotations

import inspect
from typing import Any

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from agent_nebula_platform.a2ui import A2UIActionRequest, A2UIRendererCapabilities
from agent_nebula_platform.a2ui.service import A2UIService
from agent_nebula_platform.platform.errors import (
    AgentRuntimeError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
)
from agent_nebula_platform.platform.health import HealthProvider, HealthRoutes
from agent_nebula_platform.platform.metrics import MetricsRegistry
from agent_nebula_platform.platform.transport.http import RequestTargetResolver
from agent_nebula_platform.platform.transport.rest import RestSkillAdapter
from agent_nebula_platform.security.oauth.metadata import (
    ProtectedResourceMetadataProvider,
)
from agent_nebula_platform.skills import SkillResult


def _result_document(result: SkillResult, a2ui: A2UIService | None) -> dict[str, Any]:
    """Serialize one skill result and validate any declarative UI artifact."""

    document = result.model_dump(mode="json", exclude={"ui"}, exclude_none=True)
    if result.ui is not None:
        if a2ui is None:
            raise ConfigurationError(
                "Skill returned A2UI content but the A2UI capability is not enabled"
            )
        document["ui"] = a2ui.data_part(result.ui).model_dump(mode="json")
    return document


def _bearer_token(authorization: str | None) -> str | None:
    """Extract a DPoP-bound access token without accepting other schemes."""

    if not authorization:
        return None
    scheme, separator, value = authorization.partition(" ")
    if not separator or scheme.lower() != "dpop" or not value.strip():
        return None
    return value.strip()


def _http_error(exc: AgentRuntimeError) -> HTTPException:
    """Map stable runtime exceptions to non-sensitive HTTP responses."""

    if isinstance(exc, AuthenticationError):
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    if isinstance(exc, AuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, ConfigurationError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Agent runtime request could not be fulfilled",
    )


class FastApiRuntimeAdapter:
    """Attach selected runtime capabilities to an existing FastAPI application.

    This adapter never starts Uvicorn, changes application lifespan handlers,
    or configures global middleware. The host remains responsible for process
    and server ownership.
    """

    def __init__(
        self,
        *,
        protected_resource_metadata: ProtectedResourceMetadataProvider | None = None,
        health: HealthProvider | None = None,
        health_routes: HealthRoutes | None = None,
        metrics: MetricsRegistry | None = None,
        rest: RestSkillAdapter | None = None,
        a2ui: A2UIService | None = None,
        api_prefix: str = "/api/v1",
        trust_forwarded_headers: bool = False,
        forwarded_prefix_header: str = "X-Forwarded-Prefix",
    ) -> None:
        self._protected_resource_metadata = protected_resource_metadata
        self._health = health
        self._health_routes = health_routes or HealthRoutes()
        self._metrics = metrics
        self._rest = rest
        self._a2ui = a2ui
        self._api_prefix = api_prefix.rstrip("/")
        self._request_target = RequestTargetResolver(
            trust_forwarded_headers=trust_forwarded_headers,
            forwarded_prefix_header=forwarded_prefix_header,
        )

    def attach(self, app: FastAPI) -> None:
        """Attach only configured endpoints and reject duplicate attachment."""

        marker = "_agent_nebula_platform_fastapi_attached"
        if getattr(app.state, marker, False):
            raise ConfigurationError("Agent Runtime routes are already attached")
        app.include_router(self._router())
        setattr(app.state, marker, True)

    def _router(self) -> APIRouter:
        """Build one isolated router from the enabled runtime capabilities."""

        router = APIRouter()

        if self._protected_resource_metadata is not None:

            @router.get("/.well-known/oauth-protected-resource")
            def protected_resource_document() -> dict[str, Any]:
                """Return complete authoritative RFC 9728 metadata."""

                return self._protected_resource_metadata.get_protected_resource_metadata().copy_document()

        if self._health is not None:

            async def _health_response(*, readiness: bool) -> JSONResponse:
                """Evaluate one health dimension without duplicating response policy."""

                value = self._health.readiness() if readiness else self._health.health()
                if inspect.isawaitable(value):
                    value = await value
                return JSONResponse(
                    status_code=200 if value.ready else 503,
                    content=value.model_dump(mode="json"),
                )

            @router.get(self._health_routes.health)
            async def health() -> JSONResponse:
                """Return aggregate runtime health."""

                return await _health_response(readiness=False)

            @router.get(self._health_routes.liveness)
            async def liveness() -> JSONResponse:
                """Return aggregate process and plugin liveness."""

                return await _health_response(readiness=False)

            @router.get(self._health_routes.readiness)
            async def readiness() -> JSONResponse:
                """Return aggregate runtime readiness."""

                return await _health_response(readiness=True)

        if self._metrics is not None:

            @router.get(f"{self._api_prefix}/metrics")
            def metrics() -> dict[str, Any]:
                """Return one JSON-compatible metrics snapshot."""

                return self._metrics.snapshot().model_dump(mode="json")

        if self._rest is not None:

            @router.post(f"{self._api_prefix}/skills/{{skill_id}}")
            async def rest_skill(
                skill_id: str,
                request: Request,
                body: dict[str, Any],
                authorization: str | None = Header(default=None),
                dpop: str | None = Header(default=None, alias="DPoP"),
            ) -> dict[str, Any]:
                """Invoke one REST skill through shared authentication and dispatch."""

                try:
                    result = await self._rest.invoke(
                        skill_id=skill_id,
                        payload=body,
                        access_token=_bearer_token(authorization),
                        dpop_proof=dpop,
                        http_method=request.method,
                        target_uri=self._request_target.resolve(request),
                    )
                except AgentRuntimeError as exc:
                    raise _http_error(exc) from exc
                return _result_document(result, self._a2ui)

        if self._a2ui is not None:

            @router.get(f"{self._api_prefix}/a2ui/capabilities")
            def a2ui_capabilities() -> dict[str, Any]:
                """Return the renderer-facing A2UI protocol and catalog contract."""

                return self._a2ui.capabilities().model_dump(mode="json")

            @router.post(f"{self._api_prefix}/a2ui/negotiate")
            def a2ui_negotiate(body: A2UIRendererCapabilities) -> dict[str, Any]:
                """Negotiate one compatible A2UI version and catalog subset."""

                try:
                    negotiated = self._a2ui.negotiate(body)
                except AgentRuntimeError as exc:
                    raise _http_error(exc) from exc
                return negotiated.model_dump(mode="json")

            @router.post(f"{self._api_prefix}/a2ui/actions")
            async def a2ui_action(
                request: Request,
                body: A2UIActionRequest,
                authorization: str | None = Header(default=None),
                dpop: str | None = Header(default=None, alias="DPoP"),
            ) -> dict[str, Any]:
                """Dispatch a renderer event through the owning agent skill."""

                try:
                    result = await self._a2ui.dispatch_action(
                        action=body,
                        access_token=_bearer_token(authorization),
                        dpop_proof=dpop,
                        http_method=request.method,
                        target_uri=self._request_target.resolve(request),
                    )
                except AgentRuntimeError as exc:
                    raise _http_error(exc) from exc
                return _result_document(result, self._a2ui)

        return router
