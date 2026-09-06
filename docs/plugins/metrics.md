# Metrics Plugin

`MetricsRegistry` provides process-local, thread-safe:

- counters;
- gauges;
- duration summaries.

Exporters consume immutable snapshots. The built-in HTTP exposure is JSON through `/api/v1/metrics`.

Metrics should use stable names and non-secret identifiers. Prometheus, OpenTelemetry, CloudWatch, and Azure exporters are future adapters, not current built-ins.
