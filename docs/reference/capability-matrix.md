# Capability Matrix

| Capability | Status | Introduced | Notes |
|---|---|---:|---|
| Configuration providers | Available | 1/8 | Layered managed configuration added in 8 |
| Logging/event integration | Available | 1 | Does not configure root logger in embedded mode |
| Verified TLS | Available | 1 | No `verify=False` path |
| Onboarding | Available | 1 | Resolve-before-register and recovery cache |
| Discovery | Available | 1 | Connector-backed |
| Lifecycle | Available | 1 | Explicit deregistration currently |
| OAuth client | Available | 2 | SDK-backed private_key_jwt and DPoP |
| Protected resource | Available | 2/7 | SDK-backed validation plus metadata builder |
| Skills | Available | 3 | Sync/async handlers and exact scopes |
| REST/FastAPI | Available | 3 | Opt-in route attachment |
| Agent Card | Available | 3/7 | Hosting, builder, cross-document checks |
| Health/readiness | Available | 3/9 | Plugin-level aggregation in 9 |
| A2UI | Available | 4 | Declarative validation and action dispatch |
| Presets | Available | 5 | Embedded and standalone |
| Layered configuration/secrets | Available | 8 | Home, environment, CLI, plugin controls |
| Metrics | Available | 9 | Process-local JSON snapshots |
| Telemetry | Available | 9 | Console and JSON-lines sinks |
| Scheduler and retry | Available | 9 | In-memory jobs and bounded retry |
| Distributed task store | Planned | Future | Host port exists |
| Prometheus/OpenTelemetry exporters | Planned | Future | Not built in |
| A2UI renderer/orchestrator | Planned | Agent Studio | Runtime supplies contracts only |
