# Runtime Lifecycle

## Initialization

`AgentRuntime.initialize()` performs these steps:

1. emits `runtime.initialization.started`;
2. iterates plugins in composition order;
3. runs `before_start()`;
4. runs `initialize()`;
5. runs `after_start()`;
6. marks the plugin initialized;
7. records startup duration when metrics are available;
8. publishes operational telemetry when telemetry is available;
9. emits `runtime.initialized` after all required plugins succeed.

A required plugin failure closes already-started plugins in reverse order and raises `PluginError`. An optional plugin failure is recorded and initialization continues.

## Shutdown

`AgentRuntime.close()` closes initialized plugins in reverse order:

```text
transport and background jobs
        ↓
business/runtime services
        ↓
shared HTTP clients and state resources
```

Each plugin receives:

- `before_shutdown()` while dependent services still exist;
- `close()` to release its resources;
- `after_shutdown()` for final cleanup.

Shutdown failures are aggregated and surfaced as a `PluginError` after cleanup attempts.

## Context-manager use

```python
async with runtime:
    ...
```

is equivalent to explicit `initialize()` and `close()`.

## Host integration

Existing applications should call the runtime from their own lifespan. The standalone preset wires this automatically. See [Embedded versus standalone](embedded-vs-standalone.md) and [FastAPI migration](../migration/fastapi.md).
