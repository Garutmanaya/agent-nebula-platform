"""FastAPI route protection backed by Platform OAuth protected-resource services."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.routing import compile_path

from agent_nebula_platform.platform.errors import (
    AuthenticationError,
    AuthorizationError,
)
from agent_nebula_platform.platform.transport.http import RequestTargetResolver

from .models import ProtectedResourceRequest
from .service import ProtectedResourceService


@dataclass(frozen=True, slots=True)
class ProtectedRouteDefinition:
    """Describe one existing application route protected by OAuth and DPoP."""

    path: str
    methods: tuple[str, ...]
    required_scopes: tuple[str, ...]


class ProtectedRouteInstaller:
    """Install OAuth/DPoP enforcement for selected caller-owned FastAPI routes."""

    def install(
        self,
        *,
        app: FastAPI,
        service: ProtectedResourceService,
        routes: tuple[ProtectedRouteDefinition, ...],
        trust_forwarded_headers: bool,
        forwarded_prefix_header: str,
    ) -> None:
        """Attach middleware without coupling the developer facade to FastAPI security."""

        if not routes:
            return
        resolver = RequestTargetResolver(
            trust_forwarded_headers=trust_forwarded_headers,
            forwarded_prefix_header=forwarded_prefix_header,
        )
        protected_routes = tuple(
            (method.upper(), compile_path(route.path)[0], route.required_scopes)
            for route in routes
            for method in route.methods
        )

        @app.middleware("http")
        async def protected_route_middleware(request: Request, call_next):
            scopes = next(
                (
                    required
                    for method, pattern, required in protected_routes
                    if method == request.method.upper()
                    and pattern.fullmatch(request.url.path)
                ),
                None,
            )
            if scopes is None:
                return await call_next(request)
            authorization = request.headers.get("authorization") or ""
            scheme, separator, token = authorization.partition(" ")
            if not separator or scheme.lower() != "dpop" or not token.strip():
                return JSONResponse(
                    status_code=401, content={"detail": "DPoP authorization is required"}
                )
            proof = request.headers.get("dpop")
            if not proof:
                return JSONResponse(
                    status_code=401, content={"detail": "DPoP proof is required"}
                )
            try:
                service.authenticate(
                    ProtectedResourceRequest(
                        access_token=token.strip(),
                        dpop_proof=proof,
                        http_method=request.method,
                        target_uri=resolver.resolve(request),
                        required_scopes=scopes,
                    )
                )
            except AuthenticationError as exc:
                return JSONResponse(status_code=401, content={"detail": str(exc)})
            except AuthorizationError as exc:
                return JSONResponse(status_code=403, content={"detail": str(exc)})
            return await call_next(request)
