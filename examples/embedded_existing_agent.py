"""Minimal migration example for an existing application."""
from agent_nebula_platform import AgentRuntime,MemoryStateStore,NullEventSink,RuntimeContext
from agent_nebula_platform.integrations.nebula import RestNebulaConnector
from agent_nebula_platform.integrations.nebula.onboarding import OnboardingSettings
from agent_nebula_platform.integrations.nebula.onboarding.plugin import OnboardingPlugin

def existing_payload()->dict:
    """Return the existing application's complete onboarding payload."""
    return {"entity_name":"existing-agent","authentication":{"method":"OPEN"},"roles":["AGENT"]}

async def build_runtime()->AgentRuntime:
    """Compose runtime integration without taking over host logging or server startup."""
    connector=RestNebulaConnector(base_url="https://nebula.example")
    context=RuntimeContext(connector,MemoryStateStore(),NullEventSink())
    return AgentRuntime(context=context,plugins=[OnboardingPlugin(settings=OnboardingSettings(),payload_provider=existing_payload)])
