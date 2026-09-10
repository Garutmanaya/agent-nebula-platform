"""Runtime plugin for official A2A 1.0 server transports."""

from __future__ import annotations

from a2a.server.request_handlers import RequestHandler
from a2a.types import AgentCard
from fastapi import FastAPI

from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.plugins.base import RuntimePlugin
from agent_nebula_platform.protocols.a2a.security.security import (
    A2AServerSecurityService,
)
from agent_nebula_platform.protocols.a2a.server.configuration.listener import (
    A2AServerTlsConfiguration,
)
from agent_nebula_platform.protocols.a2a.server.server_adapter import A2AServerAdapter


class A2AServerPlugin(RuntimePlugin):
    """Attach and manage interfaces declared by an official A2A Agent Card."""

    def __init__(
        self,
        *,
        app: FastAPI,
        agent_card: AgentCard,
        agent_card_route: str = "/.well-known/agent-card.json",
        request_handler: RequestHandler,
        required: bool = True,
        security: A2AServerSecurityService | None = None,
        tls: A2AServerTlsConfiguration | None = None,
    ) -> None:
        """Capture host-owned app and official A2A server components."""

        self._app = app
        self._agent_card = agent_card
        self._agent_card_route = agent_card_route
        self._request_handler = request_handler
        self._required = required
        self._security = security
        self._tls = tls or A2AServerTlsConfiguration()

    @property
    def name(self) -> str:
        """Return the stable service/plugin identifier."""

        return "a2a.server"

    @property
    def required(self) -> bool:
        """Return whether A2A interface startup failure is fatal."""

        return self._required

    async def initialize(self, context: RuntimeContext) -> None:
        """Start exactly the interfaces advertised by the official Agent Card."""

        adapter = A2AServerAdapter(
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
        """Stop Runtime-owned gRPC listeners and remove the service."""

        adapter = context.services.require(self.name, A2AServerAdapter)
        await adapter.close()
        context.services.remove(self.name)
