"""Agent document, health, and transport integration plugin."""

from __future__ import annotations

from fastapi import FastAPI

from agent_nebula_platform.a2ui.service import A2UIService
from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.health import HealthProvider, RuntimeHealthService
from agent_nebula_platform.platform.metrics import MetricsRegistry
from agent_nebula_platform.platform.plugins.base import RuntimePlugin
from agent_nebula_platform.platform.transport.fastapi import FastApiRuntimeAdapter
from agent_nebula_platform.platform.transport.rest import RestSkillAdapter
from agent_nebula_platform.security.oauth.metadata import (
    ProtectedResourceMetadataProvider,
)
from agent_nebula_platform.skills import SkillInvocationService


class AgentServerPlugin(RuntimePlugin):
    """Attach selected runtime endpoints to a caller-owned FastAPI application."""

    def __init__(
        self,
        *,
        app: FastAPI,
        protected_resource_metadata: ProtectedResourceMetadataProvider | None = None,
        health: HealthProvider | None = None,
        enable_rest: bool = True,
        enable_a2ui: bool = True,
        api_prefix: str = "/api/v1",
        trust_forwarded_headers: bool = False,
        forwarded_prefix_header: str = "X-Forwarded-Prefix",
        required: bool = True,
    ) -> None:
        self._app = app
        self._protected_resource_metadata = protected_resource_metadata
        self._health = health
        self._enable_rest = enable_rest
        self._enable_a2ui = enable_a2ui
        self._api_prefix = api_prefix
        self._trust_forwarded_headers = trust_forwarded_headers
        self._forwarded_prefix_header = forwarded_prefix_header
        self._required = required

    @property
    def name(self) -> str:
        """Return the stable plugin identifier."""

        return "transport.fastapi"

    @property
    def required(self) -> bool:
        """Return whether route attachment failure is fatal."""

        return self._required

    async def initialize(self, context: RuntimeContext) -> None:
        """Attach configured routes without starting or owning the HTTP server."""

        invocation = None
        if self._enable_rest:
            invocation = context.services.require(
                "skills.invocation", SkillInvocationService
            )
        a2ui = None
        if self._enable_a2ui and "a2ui" in context.services.names():
            a2ui = context.services.require("a2ui", A2UIService)
        runtime_health = context.services.require(
            "runtime.health", RuntimeHealthService
        )
        runtime_health.set_host_provider(self._health)
        metrics = None
        if "metrics" in context.services.names():
            metrics = context.services.require("metrics", MetricsRegistry)
        adapter = FastApiRuntimeAdapter(
            protected_resource_metadata=self._protected_resource_metadata,
            health=runtime_health,
            metrics=metrics,
            rest=RestSkillAdapter(invocation)
            if self._enable_rest and invocation
            else None,
            a2ui=a2ui,
            api_prefix=self._api_prefix,
            trust_forwarded_headers=self._trust_forwarded_headers,
            forwarded_prefix_header=self._forwarded_prefix_header,
        )
        adapter.attach(self._app)
        context.services.register(self.name, adapter)

    async def close(self, context: RuntimeContext) -> None:
        """Remove the service marker; caller-owned routes and app remain intact."""

        context.services.remove(self.name)
