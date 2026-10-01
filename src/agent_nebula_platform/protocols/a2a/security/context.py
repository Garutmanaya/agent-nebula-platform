"""Bridge Agent Nebula authentication into the official A2A server context."""

from __future__ import annotations

from a2a.server.context import ServerCallContext
from a2a.server.routes.common import DefaultServerCallContextBuilder
from starlette.exceptions import HTTPException
from starlette.requests import Request

from agent_nebula_platform.platform.errors import AuthenticationError

from .security import A2ASecurityRequest, A2AServerSecurityService


class A2ASecurityServerCallContextBuilder(DefaultServerCallContextBuilder):
    """Authenticate A2A HTTP calls while preserving the SDK server pipeline.

    AGENT NEBULA SECURITY: A2A advertises security requirements but does not
    implement the credential validation used by Agent Nebula.  This builder
    plugs Nebula's configured authenticators into the official a2a-sdk
    ``ServerCallContextBuilder`` extension point.  Route creation, request
    parsing, task handling, streaming, and dispatch remain owned by a2a-sdk.
    """

    _PRINCIPALS_STATE_KEY = "agent_nebula.security.principals"

    def __init__(self, security: A2AServerSecurityService) -> None:
        self._security = security

    def build(self, request: Request) -> ServerCallContext:
        """Build the native SDK context after enforcing AgentCard security."""

        context = super().build(request)
        if not self._security.required:
            return context

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
        except AuthenticationError as exc:
            # HTTPException is intentionally used here so the caller-owned
            # Starlette/FastAPI stack emits the transport-level 401 response.
            # The official A2A dispatcher remains responsible for A2A errors.
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        # AGENT NEBULA SECURITY: retain authenticated principals as contextual
        # state without modifying official A2A request or wire models.
        context.state[self._PRINCIPALS_STATE_KEY] = principals
        return context
