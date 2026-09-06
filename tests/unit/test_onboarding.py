import pytest

from agent_nebula_platform import (
    AgentRuntime,
    MemoryStateStore,
    NullEventSink,
    RuntimeContext,
)
from agent_nebula_platform.integrations.nebula.onboarding import OnboardingSettings
from agent_nebula_platform.integrations.nebula.onboarding.plugin import OnboardingPlugin


class Connector:
    def __init__(self):
        self.calls = []

    async def resolve_onboarding(self, payload):
        self.calls.append("resolve")

    async def onboard(self, payload):
        self.calls.append("onboard")
        return {"onboarding_id": "o", "agent_id": "a", "client_id": "c"}

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_onboarding_resolves_then_registers_and_caches():
    c = Connector()
    s = MemoryStateStore()
    p = OnboardingPlugin(
        settings=OnboardingSettings(retry_delay_seconds=0),
        payload_provider=lambda: {"entity_name": "x"},
    )
    r = AgentRuntime(context=RuntimeContext(c, s, NullEventSink()), plugins=[p])
    await r.initialize()
    assert c.calls == ["resolve", "onboard"]
    assert s.read("onboarding")["agent_id"] == "a"
    await r.close()
