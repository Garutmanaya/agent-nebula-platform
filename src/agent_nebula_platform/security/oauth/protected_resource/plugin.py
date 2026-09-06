"""Optional protected-resource capability plugin."""

from __future__ import annotations

from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.plugins.base import RuntimePlugin
from agent_nebula_platform.security.oauth.protected_resource import (
    ProtectedResourceService,
)


class ProtectedResourcePlugin(RuntimePlugin):
    """Expose provider-side OAuth and DPoP authentication to host transports."""

    def __init__(
        self, service: ProtectedResourceService, *, required: bool = True
    ) -> None:
        self.service = service
        self._required = required

    @property
    def name(self) -> str:
        """Return the stable plugin identifier."""

        return "oauth.protected_resource"

    @property
    def required(self) -> bool:
        """Return whether composition failure is fatal."""

        return self._required

    async def initialize(self, context: RuntimeContext) -> None:
        """Register the already-composed service with the runtime context."""

        context.services.register(self.name, self.service)

    async def close(self, context: RuntimeContext) -> None:
        """Remove the service without closing caller-owned dependencies."""

        context.services.remove(self.name)
