# Observability and operations

Platform services under `platform/` provide lifecycle events, health/readiness, metrics, telemetry, retry and scheduling. `observability/` provides execution tracing support. These are reusable runtime capabilities; individual applications select and configure them through composition and plugins.

- **Lifecycle:** Plugins initialize in deterministic order and shut down in reverse order. Required failures stop startup; optional failures are tracked.
- **Health/readiness:** Plugin status contributes to runtime operational state.
- **Metrics/telemetry:** Services and plugins publish measurements and typed events when configured.
- **Execution tracing:** Operational execution traces are separate from protocol wire-format handling.

See [platform lifecycle](platform.md) for the plugin contracts and integration points.
