"""Optional Agent Nebula onboarding plugin for existing and new agents."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from typing import Any

from agent_nebula_platform.integrations.nebula.onboarding.models import (
    OnboardingResult,
    OnboardingSettings,
)
from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.events import RuntimeEvent
from agent_nebula_platform.platform.health import HealthStatus
from agent_nebula_platform.platform.plugins.base import (
    RuntimePlugin,
    RuntimePluginPhase,
)

PayloadProvider = Callable[[], Mapping[str, Any]]


class OnboardingPlugin(RuntimePlugin):
    """Resolve or register one stable external identity through Agent Nebula."""

    def __init__(
        self,
        *,
        settings: OnboardingSettings,
        payload_provider: PayloadProvider,
        required: bool = True,
    ) -> None:
        self._settings = settings
        self._payload_provider = payload_provider
        self._required = required
        self.result = None

    @property
    def name(self) -> str:
        return "nebula.onboarding"

    @property
    def phase(self) -> RuntimePluginPhase:
        """Start onboarding only after the HTTPS listener is reachable."""

        return RuntimePluginPhase.POST_SERVER

    @property
    def required(self) -> bool:
        return self._required

    async def health(self) -> HealthStatus:
        """Report liveness even while onboarding has not completed."""

        return HealthStatus(status="healthy", ready=True)

    async def readiness(self) -> HealthStatus:
        """Remain unready until enabled onboarding resolves or registers."""

        if not self._settings.enabled:
            return HealthStatus(status="disabled", ready=True)
        if self.result is None:
            return HealthStatus(status="initializing", ready=False)
        return HealthStatus(status="ready", ready=True)

    async def initialize(self, context: RuntimeContext) -> None:
        if not self._settings.enabled:
            return
        cached = context.state_store.read(self._settings.state_key)
        if cached is not None:
            self.result = OnboardingResult.model_validate(cached)
        payload = dict(self._payload_provider())
        last = None
        for attempt in range(1, self._settings.retry_count + 1):
            try:
                response = None
                if self._settings.resolve_before_register:
                    response = await context.nebula.resolve_onboarding(payload)
                if response is None:
                    response = await context.nebula.onboard(payload)
                self.result = OnboardingResult.model_validate(response)
                context.state_store.write(
                    self._settings.state_key,
                    self.result.model_dump(mode="json", exclude_none=True),
                )
                context.events.emit(
                    RuntimeEvent(
                        "nebula.onboarding.completed",
                        {"attempt": attempt, "resolved": response is not None},
                    )
                )
                return
            except Exception as exc:  # noqa: BLE001 - isolate failures at runtime boundary
                last = exc
                context.events.emit(
                    RuntimeEvent(
                        "nebula.onboarding.attempt_failed", {"attempt": attempt}
                    )
                )
                if attempt < self._settings.retry_count:
                    await asyncio.sleep(self._settings.retry_delay_seconds)
        assert last is not None
        raise last
