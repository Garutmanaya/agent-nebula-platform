# Package Reference

| Package | Responsibility |
|---|---|
| `agent_runtime.runtime` | Core plugin lifecycle |
| `agent_runtime.context` / `services` | Dependency context and service registry |
| `agent_runtime.configuration` | Layered configuration and provider ports |
| `agent_runtime.connectors` | Agent Nebula connector contracts/adapters |
| `agent_runtime.onboarding` | Onboarding models and orchestration |
| `agent_runtime.oauth.client` | OAuth caller orchestration and cache |
| `agent_runtime.oauth.protected_resource` | Protected request authentication |
| `agent_runtime.skills` | Skill declarations, registry, invocation |
| `agent_runtime.agent_card` | Authoritative provider, builder, validation |
| `agent_runtime.protected_resource` | RFC metadata provider and builder |
| `agent_runtime.a2a` | Task models, store port, lifecycle service |
| `agent_runtime.a2ui` | Surface models, validation, action dispatch |
| `agent_runtime.health` | Aggregation models and service |
| `agent_runtime.metrics` | Registry and exporters |
| `agent_runtime.telemetry` | Structured event service and sinks |
| `agent_runtime.scheduler` | Background-job models and service |
| `agent_runtime.retry` | Shared retry policy/executor |
| `agent_runtime.plugins` | Capability plugins |
| `agent_runtime.presets` | Embedded and standalone composition |
| `agent_runtime.transport` | REST, A2A, and FastAPI adapters |

Use public package exports rather than importing internal implementation modules where a public export exists.
