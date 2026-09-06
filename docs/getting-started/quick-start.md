# Quick Start

This example uses embedded composition and caller-owned dependencies.

```python
from agent_runtime import AgentRuntime, MemoryStateStore, NullEventSink, RuntimeContext
from agent_runtime.connectors import RestNebulaConnector
from agent_runtime.plugins import OnboardingPlugin
from agent_runtime.onboarding import OnboardingSettings

connector = RestNebulaConnector(
    base_url="https://nebula.example.test",
    client=verified_httpx_client,
)

context = RuntimeContext(
    nebula=connector,
    state_store=MemoryStateStore(),
    events=NullEventSink(),
)

runtime = AgentRuntime(
    context=context,
    plugins=(
        OnboardingPlugin(
            settings=OnboardingSettings(),
            payload_provider=build_existing_onboarding_payload,
        ),
    ),
)

await runtime.initialize()
try:
    ...
finally:
    await runtime.close()
```

The onboarding payload remains the established Agent Nebula wire contract. Agent Runtime orchestrates resolution, registration, retry, and recoverable cache behavior; it does not invent protocol fields.

Next: [Build a first agent](first-agent.md), [Secure skill example](../examples/secure-skill.md), and [Configuration overview](../configuration/overview.md).
