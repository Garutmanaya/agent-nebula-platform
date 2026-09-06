# Plugin Architecture

## Contract

Every plugin implements `RuntimePlugin` and provides a stable `name`. Plugins may override:

```text
required
before_start
initialize
after_start
before_shutdown
close
after_shutdown
health
readiness
```

## Required versus optional

- `required=True`: initialization failure stops startup and triggers rollback.
- `required=False`: failure is recorded; unrelated plugins may continue.

This flag addresses failure semantics. It does not replace configuration-based enable/disable controls.

## Ordering

Plugin order is composition order. Shutdown order is the reverse. A plugin that consumes a service must appear after the plugin that registers it.

Typical order:

```text
managed resources
onboarding
OAuth client
protected resource
skills
A2A
A2UI
metrics / telemetry / scheduler as composed
FastAPI transport
```

Actual composition is determined by selected components and settings.

## Service registry

Plugins publish typed runtime services into `RuntimeContext.services`. Consumers retrieve them by stable names and expected types. This avoids importing implementation internals between plugins.

## Health and readiness

Every initialized plugin automatically participates in aggregated health. Plugins can report liveness separately from readiness.

## Capability settings

Preset settings use three values:

- omitted/`None`: automatically compose when dependencies exist;
- `true`: require the capability and fail if dependencies are missing;
- `false`: disable the capability even when components are supplied.

See [Plugin configuration](../configuration/plugins.md) and [Custom plugins](../plugins/custom-plugin.md).
