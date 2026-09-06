# Telemetry Plugin

Telemetry is structured operational data, distinct from application logging.

A `TelemetryEvent` contains:

- event type;
- UTC timestamp;
- severity;
- optional correlation ID;
- optional task ID;
- optional plugin name;
- non-secret attributes.

Built-in sinks:

- console sink;
- JSON-lines file sink.

Sink failures can be isolated unless configured as required. Events must never include private keys, API keys, access tokens, assertions, DPoP proofs, or complete authorization headers.
