# Agent Nebula Platform Architecture

## Dependency direction

```text
agent-nebula-sdk
        ↑
   agent-runtime
        ↑
Agent Studio and third-party agents
```

## Composition model

The runtime is a small lifecycle core plus optional plugins. Existing applications may retain their own logging, configuration, HTTP server, persistence, and process lifecycle.

```text
Host composition root
  ├── RuntimeContext
  ├── caller-owned dependencies
  └── selected plugins
          ├── onboarding
          ├── OAuth client
          ├── protected resource
          ├── skills
          ├── A2UI
          └── FastAPI agent server
```

## Checkpoint 4 request flow

```text
FastAPI REST, A2A, or A2UI action route
        ↓
transport adapter
        ↓
SkillInvocationService
        ↓
ProtectedResourceService (when scopes are required)
        ↓
agent-nebula-sdk RFC 9068 + RFC 9449 validation
        ↓
exact provider-local scope policy
        ↓
SkillRegistry
        ↓
host business handler
```

## A2UI boundary

Agent Runtime owns application-level A2UI integration:

- preserving complete declarative message documents;
- validating message ordering and surface ownership;
- enforcing a renderer-approved component catalog;
- rejecting executable content;
- serializing message streams as A2A DataParts;
- binding renderer event names to existing skills;
- routing actions through the same OAuth/DPoP and scope boundary as REST/A2A calls.

Agent Runtime does not render UI, execute local renderer functions, supply a browser component library, or trust renderer-provided roles and permissions.

A2UI messages use a flat, incremental surface model. The renderer controls visual styling and native component implementation.

## Authoritative documents

`AgentCardProvider` and `ProtectedResourceMetadataProvider` return complete source documents. The runtime performs defensive copying but does not reconstruct or reduce those documents.

At composition time, `SkillsPlugin` validates:

```text
skill.required_scopes ⊆ protected_resource.scopes_supported
```

Scope comparison is exact and performs no character, case, prefix, or namespace normalization.

## HTTP ownership

`FastApiRuntimeAdapter` attaches configured routes to a caller-owned `FastAPI` application. It does not start Uvicorn, alter global middleware, or install a lifespan automatically. The host may explicitly use `runtime_lifespan(runtime)`.

## Preset composition boundary

Checkpoint 5 introduces composition presets without changing the runtime core.

- The embedded preset assembles plugins around caller-owned infrastructure.
- The standalone preset owns only resources it creates explicitly: its HTTPX
  client, local JSON cache, FastAPI application, named console logger, and
  Uvicorn process.
- Authoritative Agent Cards, Protected Resource Metadata, skills, credentials,
  and SDK-composed OAuth services remain injected dependencies.
- Preset-created resources are closed after dependent plugins through a
  first-in, last-out managed-resource plugin.
- Paths are normalized once and constrained to the configured standalone
  runtime root.

## A2A task lifecycle boundary

The A2A task service owns task identifiers, correlation identifiers, state
transitions, cancellation, event sequencing, subscriptions, and graceful
worker shutdown. It does not implement OAuth or DPoP. Submission delegates
request authorization to the shared skill service, which delegates protocol
validation to the protected-resource service and `agent-nebula-sdk`.

Push delivery is an outbound port. Applications must map an opaque
`destination_ref` to a pre-approved destination; the runtime never accepts an
arbitrary callback URL from a task payload.


## Authoritative document construction

Agent Runtime supports two equal integration paths. Existing agents may inject complete authoritative Agent Card and RFC 9728 documents. New agents may use typed builders that retain caller-supplied extension members and validate security metadata through `agent-nebula-sdk`. Cross-document validation runs at the application-plugin boundary and never rewrites source documents.

## Configuration boundary

Checkpoint 8 resolves standalone configuration once at the composition
boundary. The loader merges built-in non-secret defaults, external INI
configuration, environment overrides, and caller-provided CLI overrides in a
fixed order. Plugins receive validated typed values and never read environment
variables or files independently.

Embedded applications may continue injecting their own configuration and
secret-provider implementations; the layered loader is optional.

## Operational runtime layer

Checkpoint 9 adds a host-neutral operations layer. `AgentRuntime` owns lifecycle
ordering only; it does not own an external monitoring service. Each initialized
plugin contributes health through the `RuntimePlugin.health()` and
`RuntimePlugin.readiness()` contracts. `RuntimeHealthService` aggregates those
contributions with the optional host health provider.

`MetricsRegistry` is process-local and thread-safe. Exporters consume immutable
snapshots, which prevents transport-specific behavior from entering business
plugins. `TelemetryService` similarly fans immutable events out to injected
sinks and isolates non-required sink failures.

`RuntimeScheduler` starts after its dependencies according to normal plugin
ordering and stops before earlier plugins because shutdown is reverse ordered.
This lets jobs use services during execution while guaranteeing that background
loops are canceled before shared HTTP clients and state stores close.


## Authoritative ecosystem requirements

See `docs/AGENT_ECOSYSTEM_DESIGN_AND_IMPLEMENTATION_REQUIREMENTS.md`. All new plugins, agents, applications, and migrations must comply with this contract.
