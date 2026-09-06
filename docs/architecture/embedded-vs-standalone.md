# Embedded Versus Standalone

## Embedded mode

Use embedded mode when the host already owns FastAPI, configuration, logging, HTTP clients, state, middleware, or process lifecycle.

Agent Runtime attaches only selected routes and services. The host calls runtime initialization and shutdown from its own lifecycle.

```python
runtime = build_embedded_runtime(
    context=existing_context,
    components=components,
    options=EmbeddedPresetOptions(app=existing_app),
)
```

## Standalone mode

Use standalone mode for Agent Studio and new agents that want built-in infrastructure:

- layered INI/environment/CLI configuration;
- runtime-root path normalization;
- verified TLS and managed HTTPX client;
- Agent Nebula REST connector;
- JSON file state cache;
- FastAPI construction;
- Uvicorn startup;
- graceful shutdown;
- isolated named console logging bridge.

```python
settings = StandaloneRuntimeSettings.from_sources()
agent = build_standalone_agent(settings=settings, components=components)
agent.run()
```

## Custom composition

Mature platforms can use `AgentRuntime` and plugins directly. This mode provides maximum control and no preset ownership assumptions.

## Decision guide

| Situation | Recommended mode |
|---|---|
| Existing production FastAPI application | Embedded |
| Agent Studio sample or test agent | Standalone |
| Existing non-FastAPI application | Direct/custom composition |
| Platform with custom DI and observability | Direct/custom composition |

See [Standalone example](../examples/standalone.md) and [Embedded example](../examples/embedded.md).
