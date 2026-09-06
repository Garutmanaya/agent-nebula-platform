"""Plugins exposing Runtime-owned A2UI session and action capabilities."""

from __future__ import annotations

from agent_nebula_platform.a2ui.actions import A2UIActionDispatcher
from agent_nebula_platform.a2ui.session import A2UISessionService
from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.plugins.base import RuntimePlugin


class A2UISessionPlugin(RuntimePlugin):
    """Register the first-class A2UI session and action services."""

    def __init__(
        self,
        service: A2UISessionService,
        *,
        dispatcher: A2UIActionDispatcher | None = None,
        required: bool = True,
    ) -> None:
        """Initialize the plugin with Runtime-owned service instances."""

        self._service = service
        self._dispatcher = dispatcher or A2UIActionDispatcher(service)
        self._required = required

    @property
    def name(self) -> str:
        """Return the stable primary service identifier."""

        return "a2ui.session"

    @property
    def required(self) -> bool:
        """Return whether initialization failure is fatal."""

        return self._required

    async def initialize(self, context: RuntimeContext) -> None:
        """Register session and action-dispatch services."""

        context.services.register(self.name, self._service)
        context.services.register("a2ui.actions", self._dispatcher)

    async def close(self, context: RuntimeContext) -> None:
        """Remove Runtime-owned A2UI services in reverse order."""

        context.services.remove("a2ui.actions")
        context.services.remove(self.name)
