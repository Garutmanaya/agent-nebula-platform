# Agent Runtime Documentation

Agent Runtime is the pluggable application-integration layer for Agent Nebula-compatible agents. It sits above `agent-nebula-sdk`: the SDK owns protocol and cryptographic behavior, while Agent Runtime owns composition, lifecycle, optional integrations, and developer-facing runtime services.

## Start here

- [Vision and goals](architecture/vision-and-goals.md)
- [Top-level architecture](architecture/architecture.md)
- [Design principles](architecture/design-principles.md)
- [Quick start](getting-started/quick-start.md)
- [Embedded versus standalone use](architecture/embedded-vs-standalone.md)
- [Plugin architecture](architecture/plugin-architecture.md)
- [Security overview](security/overview.md)
- [Capability and plugin matrix](reference/capability-matrix.md)
- [Roadmap](reference/roadmap.md)

## Documentation map

### Architecture

- [Vision and goals](architecture/vision-and-goals.md)
- [Architecture](architecture/architecture.md)
- [Design principles](architecture/design-principles.md)
- [Runtime lifecycle](architecture/runtime-lifecycle.md)
- [Plugin architecture](architecture/plugin-architecture.md)
- [Embedded versus standalone](architecture/embedded-vs-standalone.md)
- [Dependency and ownership boundaries](architecture/dependency-boundaries.md)

### Getting started

- [Installation](getting-started/installation.md)
- [Quick start](getting-started/quick-start.md)
- [Build a first agent](getting-started/first-agent.md)
- [Operational verification](getting-started/verification.md)

### Configuration and infrastructure

- [Configuration overview](configuration/overview.md)
- [Configuration precedence](configuration/precedence.md)
- [Runtime home and paths](configuration/runtime-home.md)
- [Secrets](configuration/secrets.md)
- [TLS](configuration/tls.md)
- [Plugin enablement](configuration/plugins.md)

### Plugins and capabilities

- [Plugin overview](plugins/overview.md)
- [Onboarding](plugins/onboarding.md)
- [Discovery and lifecycle](plugins/discovery-lifecycle.md)
- [OAuth client](plugins/oauth-client.md)
- [Protected resource](plugins/protected-resource.md)
- [Skills](plugins/skills.md)
- [REST and FastAPI](plugins/rest-fastapi.md)
- [A2A](plugins/a2a.md)
- [A2UI](plugins/a2ui.md)
- [Agent Card and resource metadata](plugins/documents.md)
- [Health](plugins/health.md)
- [Metrics](plugins/metrics.md)
- [Telemetry](plugins/telemetry.md)
- [Scheduler and retry](plugins/scheduler-retry.md)
- [Custom plugins](plugins/custom-plugin.md)

### Security

- [Security overview](security/overview.md)
- [OAuth and DPoP](security/oauth-dpop.md)
- [Scope policy](security/scopes.md)
- [A2UI trust boundary](security/a2ui.md)
- [Operational data](security/operational-data.md)

### Runtime behavior

- [Runtime context and services](runtime/context-and-services.md)
- [State and authority](runtime/state-and-authority.md)
- [Observability](runtime/observability.md)
- [Background jobs and shutdown](runtime/background-jobs.md)

### Migration and integration

- [Migration overview](migration/overview.md)
- [Existing FastAPI application](migration/fastapi.md)
- [Existing configuration and logging](migration/configuration-logging.md)
- [Agent Genesis migration](migration/agent-genesis.md)
- [Third-party integration checklist](migration/third-party-checklist.md)

### Examples and reference

- [Standalone composition](examples/standalone.md)
- [Embedded composition](examples/embedded.md)
- [Secure skill invocation](examples/secure-skill.md)
- [A2UI skill result](examples/a2ui.md)
- [Package reference](reference/package-reference.md)
- [Terminology](reference/terminology.md)
- [Capability matrix](reference/capability-matrix.md)
- [Roadmap](reference/roadmap.md)

## Current release boundary

The documentation describes the implemented `0.9.x` runtime. Planned functionality is identified explicitly in the [roadmap](reference/roadmap.md); it is not presented as available.
