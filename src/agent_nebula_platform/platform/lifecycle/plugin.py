"""Optional workload lifecycle integration."""

from __future__ import annotations

from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.events import RuntimeEvent
from agent_nebula_platform.platform.plugins.base import RuntimePlugin


class LifecyclePlugin(RuntimePlugin):
    """Expose explicit self-deregistration without owning host shutdown policy."""

    def __init__(
        self,
        *,
        external_agent_id: str,
        agent_id_provider,
        agent_token_provider,
        state_key: str = "onboarding",
        required: bool = False,
    ) -> None:
        self._external = external_agent_id
        self._agent_id_provider = agent_id_provider
        self._token_provider = agent_token_provider
        self._state_key = state_key
        self._required = required
        self._context = None

    @property
    def name(self) -> str:
        return "nebula.lifecycle"

    @property
    def required(self) -> bool:
        return self._required

    async def initialize(self, context: RuntimeContext) -> None:
        self._context = context

    async def deregister(
        self, *, reason: str, correlation_id: str | None = None
    ) -> dict:
        """Deregister the workload and clear only its non-authoritative local cache."""
        if self._context is None:
            raise RuntimeError("Lifecycle plugin is not initialized")
        result = await self._context.nebula.deregister(
            external_agent_id=self._external,
            agent_id=self._agent_id_provider(),
            agent_token=self._token_provider(),
            reason=reason,
            correlation_id=correlation_id,
        )
        self._context.state_store.delete(self._state_key)
        self._context.events.emit(
            RuntimeEvent(
                "nebula.lifecycle.deregistered", {"external_agent_id": self._external}
            )
        )
        return result

    async def close(self, context: RuntimeContext) -> None:
        del context
        self._context = None
