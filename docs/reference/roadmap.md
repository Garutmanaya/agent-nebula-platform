# Roadmap

## Next ecosystem work

### Agent Studio foundation

- repository structure;
- shared fleet configuration;
- in-memory fixtures;
- common orchestrator boundary;
- A2UI renderer boundary;
- startup, registration, and verification scripts.

### First Agent Genesis migration

- migrate one Provider Agent to Agent Runtime;
- compare Agent Card, onboarding, OAuth, DPoP, scopes, A2A, lifecycle, and health behavior;
- remove duplicated runtime infrastructure after regression success.

### Configurable reference fleet

- multiple Publishers and Providers;
- Provider, client, and hybrid agents;
- Parking, Airline, Hotel, CloudOps, Retail, and Finance categories;
- real OAuth and DPoP;
- database-free deterministic services;
- A2UI surfaces and actions.

## Runtime enhancements after integration feedback

- task leasing, expiration, cleanup, retry, and worker coordination;
- full external A2A schema conformance through SDK evolution;
- A2UI streaming and renderer capability negotiation;
- Prometheus and OpenTelemetry exporters;
- cloud telemetry adapters;
- distributed scheduler/leader election;
- cloud secret-manager adapters;
- automatic Agent Nebula heartbeat and synchronization jobs;
- migration toolkit and compatibility report.

## Public-release hardening

- packaging and compatibility policy;
- complete integration and negative-security tests;
- load and concurrency tests;
- accessibility and documentation review;
- public API stability review;
- contributor and release processes.

Planned items are not supported features until implemented and tested.
