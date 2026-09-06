# Top-Level Architecture

## Layered design

```text
┌──────────────────────────────────────────────────────────┐
│ Agent Studio or third-party business application        │
│ skills, domain services, existing server, existing data │
└────────────────────────────┬─────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────┐
│ Agent Runtime                                            │
│ plugin lifecycle, composition, transport adapters,      │
│ onboarding, skills, tasks, A2UI, operations             │
└────────────────────────────┬─────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────┐
│ agent-nebula-sdk                                        │
│ OAuth, JOSE, JWT, JWK, RFC 7638, RFC 8707, RFC 9068,   │
│ RFC 9449, protocol validation                           │
└────────────────────────────┬─────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────┐
│ Agent Nebula and protected provider agents              │
└──────────────────────────────────────────────────────────┘
```

## Runtime core

The core is intentionally small:

- `AgentRuntime` initializes plugins in declared order and closes them in reverse order.
- `RuntimeContext` carries caller-owned dependencies and a typed service registry.
- `RuntimePlugin` defines lifecycle hooks plus health and readiness contracts.
- `PluginRegistry` tracks plugin state and rejects duplicate names.
- required plugin failures roll back already-started plugins; optional failures are isolated.

## Optional capabilities

Capabilities are composed as plugins rather than embedded in the core:

```text
onboarding
OAuth client
protected resource
skills
Agent Card and metadata publication
REST/FastAPI
A2A immediate invocation and tasks
A2UI
health
metrics
telemetry
scheduler
managed resources
```

See the [capability matrix](../reference/capability-matrix.md).

## Request boundary

```text
REST, A2A, or A2UI action route
        ↓
transport adapter
        ↓
SkillInvocationService
        ↓
ProtectedResourceService when scopes are required
        ↓
agent-nebula-sdk token and DPoP validation
        ↓
exact provider-local scope authorization
        ↓
registered business skill
```

Transport adapters remain thin. Business handlers receive a validated `SkillInvocation`; they do not implement token parsing or DPoP validation.

## Operational boundary

```text
RuntimePlugin.health/readiness
        ↓
RuntimeHealthService
        ↓
/health and /ready

MetricsRegistry → JSON exporter → /api/v1/metrics
TelemetryService → caller-approved sinks
RuntimeScheduler → startup/once/interval/shutdown jobs
```

## Authority

Agent Nebula remains authoritative for registration identity, ownership, lifecycle, OAuth identifiers, and trust state. Runtime files are caches or host-owned state, not the source of truth.

Related: [Runtime lifecycle](runtime-lifecycle.md), [Plugin architecture](plugin-architecture.md), [State and authority](../runtime/state-and-authority.md).
