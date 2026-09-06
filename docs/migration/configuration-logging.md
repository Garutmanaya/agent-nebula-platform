# Existing Configuration and Logging

## Configuration

Implement or adapt the configuration-provider port, or build typed runtime components directly from the host's settings. The built-in layered loader is optional.

## Logging

Library mode uses semantic events and standard named loggers without installing handlers or changing the root logger. Existing applications can:

- inject a custom event sink;
- bridge runtime events to structured logging;
- select telemetry sinks;
- disable the standalone console bridge.

Do not copy secrets into log-context mappings.
