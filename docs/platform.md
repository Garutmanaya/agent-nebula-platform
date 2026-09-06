# Platform Infrastructure

## Purpose

`agent_nebula_platform.platform` contains protocol-independent runtime machinery. It is the composition and lifecycle foundation used by A2A, OAuth, skills, A2UI, integrations, and future protocol plugins.

## Major areas

```text
platform/
├── plugins/
├── configuration/
├── lifecycle/
├── presets/
├── capabilities/
├── health/
├── metrics/
├── telemetry/
├── scheduler/
├── retry/
├── transport/
├── context.py
├── services.py
├── runtime.py
├── state.py
├── tls.py
├── events.py
├── discovery.py
└── execution_trace.py
```

## Runtime context and services

`RuntimeContext` is the dependency context supplied to plugins. Shared runtime services are registered by stable service names rather than through imports between unrelated concrete plugins. This allows a plugin to consume an already initialized capability without making the generic plugin framework aware of that implementation.

## Plugin contract

Every plugin implements `RuntimePlugin` and provides:

- stable `name`;
- lifecycle boundary (`PRE_SERVER` by default or `POST_SERVER`);
- `required` startup policy;
- `before_start`, `initialize`, and `after_start` hooks;
- `before_shutdown`, `close`, and `after_shutdown` hooks;
- `health` and `readiness`.

`PluginRegistry` rejects duplicate names, preserves registration order, and tracks enabled, initialized and failed states.

## Runtime lifecycle

`AgentRuntime` owns deterministic lifecycle execution.

```text
composition
    ↓
PluginRegistry
    ↓
initialize PRE_SERVER plugins in order
    ↓
server/listener availability boundary
    ↓
initialize POST_SERVER plugins in order
    ↓
runtime operation
    ↓
close initialized plugins in reverse order
```

If a required plugin fails initialization, runtime startup fails and already-started plugins are closed. Optional plugin failures are recorded without failing the whole runtime. Shutdown attempts to close all started plugins and reports aggregated failure through the runtime boundary.

## Composition presets

`platform/presets/` provides embedded and standalone composition roots.

`RuntimeFeatureComponents` is the typed input containing host-supplied skills, security services, A2A components, A2UI capabilities, health, metrics, telemetry, scheduling and optional onboarding components.

`RuntimePluginSettings` controls capability selection. Each setting is tri-state:

- `False`: do not install the capability;
- `True`: require the capability and fail if required components are absent;
- `None`: enable automatically when the required component is available.

`compose_feature_plugins()` converts those components/settings into a dependency-safe plugin sequence. Concrete plugins are created by their owning functional modules, not by `platform/plugins/`.

### Embedded composition

Embedded mode is for an application that already owns its FastAPI application and process lifecycle. Platform attaches selected capabilities to caller-owned infrastructure.

### Standalone composition

Standalone mode provides Platform-owned application composition around the same plugin and component contracts, including configuration and server-oriented infrastructure.

## Configuration

`platform/configuration/` provides application configuration loading, INI providers, layered settings, environment/CLI sources, path resolution, runtime home handling, and secret/configuration ports.

Protocol configuration should remain with the protocol. Product integration configuration should remain with the integration. Generic runtime/deployment configuration belongs here.

## Lifecycle and transport

`platform/lifecycle/` connects runtime lifecycle to host/server lifecycle. `platform/transport/` contains reusable FastAPI, HTTP, HTTP-client, and REST infrastructure. These modules provide transport mechanics; protocol semantics remain under `protocols/`.

## Health

The health package provides health models/providers and runtime health aggregation. Plugin `health()` and `readiness()` methods allow operational status to be reported without exposing plugin implementation details.

## Metrics

The metrics package contains metric models, registry, exporters, and `MetricsPlugin`. When metrics are registered, runtime startup duration and other operational measurements can be recorded without making metrics mandatory.

## Telemetry

Telemetry contains typed events, sinks, service composition, and `TelemetryPlugin`. Runtime publishes lifecycle telemetry only when the telemetry service is present.

## Scheduler

The scheduler package provides scheduled-job models/service and `SchedulerPlugin`. Scheduled work is optional and participates in the same lifecycle as other capabilities.

## Retry

The retry package provides reusable retry policy and execution infrastructure. Retry behavior is infrastructure and should not be independently reimplemented by each protocol adapter.

## State, events and tracing

State services support runtime persistence concerns. Runtime events expose lifecycle transitions. Execution tracing provides a shared operational tracing model. These are generic facilities and therefore remain independent of A2A, A2UI, or Nebula integration.

## Capability placement rule

Use this ownership test when adding code:

```text
External protocol semantics?       → protocols/<protocol>/
Reusable operational security?     → security/<mechanism>/
Business capability invocation?    → skills/
Declarative agent UI?              → a2ui/
Specific external product/service? → integrations/<name>/
Generic runtime infrastructure?    → platform/
Standards/security primitive?      → agent-nebula-sdk
```
