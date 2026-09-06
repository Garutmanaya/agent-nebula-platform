# Health Plugin

Every initialized plugin can contribute liveness and readiness through `RuntimePlugin.health()` and `RuntimePlugin.readiness()`.

`RuntimeHealthService` aggregates:

- optional host health;
- each initialized plugin;
- stable component names and status details.

`/health` reports liveness. `/ready` reports whether the runtime is ready to serve dependent operations.

Health must not expose secrets, tokens, certificate contents, or internal stack traces.
