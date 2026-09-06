# Vision and Goals

## Vision

Agent Runtime is the official developer integration layer for Agent Nebula-compatible agents. Its purpose is to let new and existing agents adopt secure Agent Nebula registration, discovery, OAuth, DPoP, A2A, A2UI, lifecycle, and operational capabilities without rewriting their business logic or surrendering control of their application architecture.

```text
Agent or host application
        ↓
Agent Runtime
        ↓
agent-nebula-sdk
        ↓
Agent Nebula and protected agents
```

## Primary goals

1. **Simple adoption for existing agents.** Existing FastAPI applications, custom configuration systems, logging frameworks, persistence layers, and process managers can retain ownership of those concerns.
2. **Ready-to-run support for new agents.** Agent Studio and greenfield agents can opt into standalone presets that provide configuration, verified TLS, HTTP clients, FastAPI composition, state cache, logging bridge, and graceful lifecycle management.
3. **One protocol implementation.** OAuth, JOSE, JWT, JWK, DPoP, RFC behavior, and protocol validation remain in `agent-nebula-sdk`; Agent Runtime composes and exposes them.
4. **Plugin-level modularity.** Every optional capability can be selected, disabled, replaced, or omitted.
5. **Fail-closed security.** Missing authentication metadata, invalid scopes, broken trust configuration, or required-plugin failures stop the affected operation instead of silently weakening security.
6. **Preservation of authoritative documents.** Agent Cards and Protected Resource Metadata remain complete source documents; unknown extensions are preserved.
7. **Operational visibility.** Health, readiness, metrics, telemetry, scheduler jobs, and retry behavior are first-class runtime capabilities.
8. **Third-party suitability.** The public API does not require Agent Genesis naming or assumptions.

## Non-goals

Agent Runtime is not:

- an LLM framework;
- a database abstraction;
- an Agent Nebula server implementation;
- a replacement for the host application's business architecture;
- a second implementation of OAuth, JOSE, JWT, JWK, DPoP, A2A security, or TLS cryptography;
- a browser renderer for A2UI;
- a distributed task queue or distributed scheduler in the current release.

## Ecosystem position

```text
agent-nebula        Enterprise control plane
agent-nebula-sdk    Protocol and security implementation
agent-runtime       Agent developer integration and runtime layer
agent-studio        Reference agents, A2UI showcase, and test fleet
```

See [Architecture](architecture.md), [Dependency boundaries](dependency-boundaries.md), and [Roadmap](../reference/roadmap.md).
