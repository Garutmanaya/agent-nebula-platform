# Operational Data Security

Metrics and telemetry may contain:

- stable event names;
- plugin names;
- counts and durations;
- correlation and task IDs;
- outcomes and non-secret diagnostic attributes.

They must not contain:

- passwords;
- API keys;
- private keys;
- access or refresh tokens;
- client assertions;
- DPoP proofs;
- complete Authorization headers;
- full certificate/private-key material.

JSON-lines telemetry files require operating-system permissions appropriate for operational metadata. External sinks are caller-approved integrations.
