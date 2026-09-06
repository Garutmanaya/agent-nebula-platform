"""Plugin lifecycle, startup phase, and operational health contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.health import HealthStatus


class RuntimePluginPhase(StrEnum):
    """Identify the server-availability boundary required by a plugin.

    ``PRE_SERVER`` plugins prepare local state, routes, documents, and services
    before the ASGI listener starts. ``POST_SERVER`` plugins may call Agent
    Nebula or another remote service that must be able to call back into the
    agent's already-listening HTTPS endpoint.
    """

    PRE_SERVER = "pre_server"
    POST_SERVER = "post_server"


class RuntimePlugin(ABC):
    """Optional runtime capability initialized by the composition root."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return a stable plugin identifier."""

    @property
    def phase(self) -> RuntimePluginPhase:
        """Return the lifecycle phase in which this plugin must initialize."""

        return RuntimePluginPhase.PRE_SERVER

    @property
    def required(self) -> bool:
        """Return whether initialization failure must fail runtime startup."""

        return True

    async def before_start(self, context: RuntimeContext) -> None:
        """Run a pre-initialization hook before plugin resources are created."""

        del context

    @abstractmethod
    async def initialize(self, context: RuntimeContext) -> None:
        """Initialize the plugin using caller-owned dependencies."""

    async def after_start(self, context: RuntimeContext) -> None:
        """Run a post-initialization hook after the plugin becomes available."""

        del context

    async def before_shutdown(self, context: RuntimeContext) -> None:
        """Run a pre-close hook while dependent services are still available."""

        del context

    async def close(self, context: RuntimeContext) -> None:
        """Release plugin resources during reverse-order shutdown."""

        del context

    async def after_shutdown(self, context: RuntimeContext) -> None:
        """Run a final hook after plugin-owned resources have been released."""

        del context

    async def health(self) -> HealthStatus:
        """Return plugin liveness without exposing implementation internals."""

        return HealthStatus(status="healthy", ready=True)

    async def readiness(self) -> HealthStatus:
        """Return whether the plugin is ready to serve dependent operations."""

        return await self.health()
