# Agent Nebula Platform

Agent Nebula Platform is the pluggable developer integration layer for Agent Nebula-compatible agents. It depends on `agent-nebula-sdk` for OAuth, JOSE, JWT, JWK, DPoP, A2A security, and RFC behavior while giving existing and new agents optional application-level integrations.

The runtime never configures global logging, disables TLS verification, starts a server, or takes over host configuration unless the caller explicitly selects a built-in plugin or preset that provides that behavior.

## Documentation

The consolidated architecture, plugin, security, configuration, migration, example, and roadmap documentation is available at [`docs/README.md`](docs/README.md).

## Current capabilities

- recoverable Agent Nebula onboarding, discovery, and lifecycle integration;
- OAuth client and protected-resource services based on `agent-nebula-sdk`;
- authoritative Agent Card and RFC 9728 metadata hosting;
- typed skill registry with exact method-specific scopes;
- shared REST and A2A method dispatch;
- optional FastAPI route attachment;
- health and readiness endpoints;
- declarative A2UI v0.9.1 surface streams;
- approved-component catalog enforcement;
- rejection of executable UI content;
- A2A-compatible `application/a2ui+json` DataPart serialization;
- renderer action routing through the existing OAuth/DPoP-protected skill boundary;
- renderer capability discovery and explicit A2UI version/catalog negotiation;
- component-reference, catalog, and action-binding validation.


## Agent Card and Protected Resource Metadata builders

Checkpoint 7 supports both existing authoritative documents and runtime-assisted typed construction. Existing applications can continue injecting complete raw documents through `StaticAgentCardProvider` and `StaticProtectedResourceMetadataProvider`. Builders are opt-in and never reduce unknown extension fields.

```python
from agent_runtime.agent_card import AgentCardBuilder, AgentSkillDescriptor
from agent_runtime.protected_resource import ProtectedResourceMetadataBuilder

agent_card = (
    AgentCardBuilder({"vendor_extension": {"enabled": True}})
    .identity(external_agent_id="airline-agent", display_name="Airline Agent")
    .skills((
        AgentSkillDescriptor(
            id="airline.search",
            required_scopes=("airline.search",),
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        ),
    ))
    .build()
)

resource_metadata = (
    ProtectedResourceMetadataBuilder()
    .resource("https://airline.example.test")
    .authorization_servers(("https://nebula.example.test",))
    .scopes_supported(("airline.search",))
    .dpop(required=True, algorithms=("ES256",))
    .build()
)
```

At runtime initialization, configured skills are checked against the authoritative Agent Card and Protected Resource Metadata. Scope values are compared exactly and are never normalized.

## Local workspace

Until `agent-nebula-sdk` is published, use sibling repositories:

```text
workspace/
├── agent-nebula-sdk/
└── agent-runtime/
```

```bash
uv sync --extra test
uv run pytest -q
```

## A2UI skill result

```python
from agent_runtime.a2ui import A2UIMessage, A2UISurface
from agent_runtime.skills import SkillInvocation, SkillResult

async def search_flights(invocation: SkillInvocation) -> SkillResult:
    surface = A2UISurface(
        surface_id="flight-results",
        messages=(
            A2UIMessage(document={
                "version": "v0.9.1",
                "createSurface": {
                    "surfaceId": "flight-results",
                    "catalogId": "urn:agent-nebula:a2ui:travel",
                },
            }),
            A2UIMessage(document={
                "version": "v0.9.1",
                "updateComponents": {
                    "surfaceId": "flight-results",
                    "components": [
                        {"id": "root", "component": "Column", "children": ["title"]},
                        {"id": "title", "component": "Text", "text": "Flights"},
                    ],
                },
            }),
        ),
    )
    return SkillResult(data={"flights": []}, ui=surface)
```

The `A2UIPlugin` validates component names against a caller-approved catalog. Agent Runtime never executes HTML, JavaScript, CSS, or arbitrary browser code supplied by an agent.

A renderer can inspect and negotiate the public contract through:

```text
GET  /api/v1/a2ui/capabilities
POST /api/v1/a2ui/negotiate
```

Negotiation selects a common protocol version and the intersection of renderer-supported and Runtime-approved catalog features; it does not grant access to a skill.

## Renderer action flow

```text
renderer event
    ↓
POST /api/v1/a2ui/actions
    ↓
A2UIService action binding
    ↓
SkillInvocationService
    ↓
OAuth access-token + DPoP validation
    ↓
exact skill scope authorization
    ↓
business handler
```

## Endpoints supplied when enabled

```text
GET  /.well-known/agent-card.json
GET  /.well-known/oauth-protected-resource
GET  /health
GET  /ready
POST /api/v1/skills/{skill_id}
POST /api/v1/a2ui/actions
POST /a2a
```

The host still owns Uvicorn, TLS listener configuration, middleware, logging, and process lifecycle.

## Checkpoint 5 presets

Agent Runtime now provides two opt-in composition presets.

### Embedded preset

Use the embedded preset when an existing application already owns FastAPI,
configuration, logging, HTTP clients, state, and process lifecycle.

```python
runtime = build_embedded_runtime(
    context=existing_context,
    components=RuntimeFeatureComponents.create(
        skill_definitions=skills,
        agent_card=agent_card_provider,
        protected_resource_metadata=resource_metadata_provider,
        protected_resource=protected_resource_service,
    ),
    options=EmbeddedPresetOptions(app=existing_fastapi_app),
)
```

The host should initialize and close the runtime through its existing lifespan.

### Standalone preset

Use the standalone preset for Agent Studio and new agents that want built-in
INI loading, isolated console event logging, verified TLS/HTTPX connectivity,
JSON state cache, FastAPI route composition, Uvicorn startup, and graceful
shutdown.

```python
settings = StandaloneRuntimeSettings.from_ini(Path("application.conf"))
agent = build_standalone_agent(
    settings=settings,
    components=RuntimeFeatureComponents.create(
        skill_definitions=skills,
        agent_card=agent_card_provider,
        protected_resource_metadata=resource_metadata_provider,
        health=health_provider,
        oauth_client=oauth_client_service,
        protected_resource=protected_resource_service,
    ),
)
agent.run()
```

Install the explicit server dependency with:

```bash
uv sync --extra standalone --extra test
```

The standalone preset does not construct cryptographic or OAuth protocol
services itself. Those services must be composed from `agent-nebula-sdk` and
injected, preserving one implementation of OAuth, JOSE, JWT, JWK, and DPoP.

## A2A asynchronous tasks

Checkpoint 6 adds an opt-in task lifecycle on top of the existing secure skill
boundary. The runtime exposes immediate invocation for compatibility and may
also expose:

```text
POST /a2a/tasks
GET  /a2a/tasks/{task_id}
POST /a2a/tasks/{task_id}/cancel
GET  /a2a/tasks/{task_id}/events
```

Protected task submissions authenticate OAuth and DPoP before a task is
created. The validated caller identity is retained as task ownership metadata;
status, cancellation, and event-stream operations must authenticate as the
same subject and client. The in-memory store is the default single-process
implementation, while durable or distributed stores are injected through the
`A2ATaskStore` port.

## Layered configuration

Standalone mode supports the following precedence, from lowest to highest:

```text
built-in non-secret defaults
→ $AGENT_RUNTIME_HOME/config/application.conf
→ AGENT_RUNTIME__SECTION__FIELD environment variables
→ explicit CLI override mapping or key=value sequence
```

`AGENT_RUNTIME_HOME` is mandatory when the caller does not supply an explicit
runtime root. `AGENT_RUNTIME_CONFIG` may select another configuration file.
Managed paths are normalized once beneath the runtime root and path escape is
rejected.

Example environment override:

```bash
export AGENT_RUNTIME_HOME=/opt/airline-agent
export AGENT_RUNTIME__SERVER__PORT=8443
export AGENT_RUNTIME__PLUGINS__A2A=true
```

Plugin values may be omitted for automatic composition, set to `true` to
require the capability, or set to `false` to disable it. Explicit enablement
fails closed when the corresponding component is absent.

## Checkpoint 9 operational capabilities

Agent Runtime exposes operational behavior through optional plugins rather than
requiring one observability stack:

- plugin-level liveness and readiness aggregation;
- counters, gauges, duration summaries, and a JSON metrics endpoint;
- structured telemetry with caller-approved sinks;
- startup, shutdown, one-shot, and interval background jobs;
- bounded fixed, linear, or exponential retry policies;
- plugin lifecycle hooks and reverse-order graceful shutdown.

Operational plugins are opt-in in embedded applications. A standalone or Agent
Studio composition can enable them through `[runtime.plugins]`:

```ini
[runtime.plugins]
health = true
metrics = true
telemetry = true
scheduler = true
```

The host still supplies telemetry destinations and scheduled jobs. Enabling a
capability never creates cloud accounts, arbitrary callbacks, or global logging
configuration. When metrics are enabled, the built-in FastAPI adapter exposes:

```text
GET /api/v1/metrics
```

The health endpoints aggregate the host provider and initialized plugin
contributions:

```text
GET /health
GET /ready
```

## Listener-ready onboarding

Agent Runtime separates local endpoint preparation from callback-dependent onboarding. Standalone agents use the built-in Uvicorn server integration, while embedded hosts signal server readiness explicitly. See [server-ready lifecycle](docs/architecture/server-ready-lifecycle.md).


## Authoritative ecosystem requirements

See `docs/AGENT_ECOSYSTEM_DESIGN_AND_IMPLEMENTATION_REQUIREMENTS.md`. All new plugins, agents, applications, and migrations must comply with this contract.
