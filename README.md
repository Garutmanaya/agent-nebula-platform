# Agent Nebula Platform

`agent-nebula-platform` is the pluggable runtime and integration layer used to build and host secure AI agents. It provides protocol adapters, security composition, skills, A2UI services, Agent Nebula integration, lifecycle management, configuration, health, telemetry, metrics, scheduling, and transport infrastructure without forcing every agent to use every capability.

The repository sits between developer-facing agent APIs and the lower-level standards implementation:

```text
agent-nebula-secureagent
        ↓
agent-nebula-platform
        ↓
agent-nebula-sdk
```

`agent-nebula-platform` depends on `agent-nebula-sdk` for reusable security and standards primitives. Platform code composes those primitives into operational capabilities such as OAuth clients and protected resources; it does not duplicate OAuth, JOSE, JWT, JWK, DPoP, or related RFC implementations.

The A2A integration uses the official `a2a-sdk` implementation and adds Platform-owned configuration, client/server integration, security interpretation, and lifecycle composition around it.

## What the Platform supports

The current codebase provides:

- official A2A 1.0 server and client integration;
- A2A security-scheme interpretation and authentication integration;
- OAuth client, dynamic client registration, authorization-server metadata, protected-resource metadata, and protected-resource services backed by `agent-nebula-sdk`;
- typed, transport-neutral skills with exact scope requirements;
- declarative A2UI surfaces, actions, sessions, validation, persistence, and capability negotiation;
- optional Agent Nebula onboarding and registration integration;
- embedded and standalone application composition;
- deterministic plugin lifecycle with pre-server and post-server initialization phases;
- FastAPI and HTTP transport infrastructure;
- health/readiness, metrics, telemetry, scheduling, retry, events, execution tracing, state, and configuration services.

MCP is a planned protocol integration boundary but is not implemented in the current repository. See [`docs/mcp.md`](docs/mcp.md).

## Repository structure

```text
src/agent_nebula_platform/
├── protocols/
│   └── a2a/
│       ├── client/             # A2A discovery, credentials, security and invocation
│       ├── security/           # Agent Card security interpretation and authenticators
│       └── server/             # A2A server adapter, execution and plugin integration
├── security/
│   └── oauth/
│       ├── client/             # OAuth client runtime services
│       ├── metadata/           # Authorization/resource metadata handling
│       ├── protected_resource/ # Token validation, authorization and route protection
│       └── registration/       # OAuth client registration integration
├── skills/                     # Protocol-neutral skill model, registry and invocation
├── a2ui/                       # Declarative UI, actions, sessions and validation
├── integrations/
│   └── nebula/                 # Optional Agent Nebula integration
└── platform/
    ├── plugins/                # Generic plugin contract and registry
    ├── configuration/          # Configuration sources, paths and application config
    ├── lifecycle/              # Host/server lifecycle integration
    ├── presets/                # Embedded and standalone composition roots
    ├── health/                 # Health/readiness services
    ├── metrics/                # Metrics registry/exporters/plugin
    ├── telemetry/              # Telemetry events, sinks and plugin
    ├── scheduler/              # Scheduled jobs and plugin
    ├── retry/                  # Retry policy/execution
    ├── transport/              # FastAPI, HTTP and REST transport infrastructure
    └── ...                     # Context, services, state, TLS, events and tracing
```

Protocol-specific behavior belongs under `protocols/`. Reusable operational security belongs under `security/`. Product-specific external integrations belong under `integrations/`. Generic runtime machinery belongs under `platform/`.

## Plugin model

A Platform plugin implements `RuntimePlugin`. Every plugin has a stable `name`, a lifecycle boundary, a `required` policy, initialization/shutdown hooks, and health/readiness methods.

Two lifecycle boundaries are supported:

- `PRE_SERVER`: prepares local services, routes, security, skills, documents, and other resources before the listener becomes available.
- `POST_SERVER`: initializes capabilities that require the agent endpoint to already be reachable, such as Agent Nebula onboarding that can cause a callback to the agent.

`PluginRegistry` preserves deterministic registration order, rejects duplicate plugin names, and tracks lifecycle status. `AgentRuntime` initializes plugins in registration order and shuts them down in reverse order. A required plugin failure fails startup; an optional plugin failure is isolated and recorded.

Concrete plugins remain with the capability they implement. For example:

```text
skills/plugin.py
protocols/a2a/server/plugin.py
security/oauth/client/plugin.py
security/oauth/protected_resource/plugin.py
integrations/nebula/onboarding/plugin.py
a2ui/plugin.py
platform/metrics/plugin.py
```

Only the generic plugin contract and registry live under `platform/plugins/`.

## Combining plugins

Applications may supply plugins directly to `AgentRuntime`, or use the embedded/standalone composition presets. The presets accept `RuntimeFeatureComponents` and plugin settings, determine which capabilities are available and enabled, and produce plugins in dependency-safe order.

Conceptually:

```python
runtime = AgentRuntime(
    context=context,
    plugins=(
        oauth_plugin,
        protected_resource_plugin,
        skills_plugin,
        a2a_plugin,
        server_plugin,
        onboarding_plugin,
    ),
)

await runtime.initialize_pre_server()
# Start/listen when the host owns the server boundary.
await runtime.initialize_post_server()
```

The preset composer follows the same model. A capability configured as `False` is omitted. A capability configured as `True` must have its required component or composition fails closed. A `None` setting enables the capability automatically when its required component is supplied.

This keeps plugin selection explicit while allowing higher-level APIs to assemble a secure agent from configuration.

## Dependency rules

The repository follows these boundaries:

```text
SecureAgent → Platform → SDK
```

- Platform must not depend on `agent-nebula-secureagent`.
- SDK must not depend on Platform.
- Protocol modules may use Platform infrastructure and operational security services.
- Platform security services delegate standards-level security behavior to `agent-nebula-sdk`.
- Agent Nebula Registry integration is optional; A2A operation does not require Registry integration.

## Documentation

Detailed documentation is organized by capability:

- [`docs/a2a.md`](docs/a2a.md) — A2A client, server, security and configuration architecture.
- [`docs/security.md`](docs/security.md) — OAuth and security layering.
- [`docs/skills.md`](docs/skills.md) — skill model, registration and invocation.
- [`docs/a2ui.md`](docs/a2ui.md) — A2UI surfaces, actions, sessions and validation.
- [`docs/integrations.md`](docs/integrations.md) — optional Agent Nebula integration.
- [`docs/mcp.md`](docs/mcp.md) — MCP status and intended protocol boundary.
- [`docs/platform.md`](docs/platform.md) — plugins, lifecycle, presets, configuration and operational services.

## Development

The project requires Python 3.12. In a sibling-repository workspace, `uv` can use the editable SDK source configured in `pyproject.toml`:

```text
workspace/
├── agent-nebula-sdk/
└── agent-nebula-platform/
```

Run validation with:

```bash
make lint
make test
```
