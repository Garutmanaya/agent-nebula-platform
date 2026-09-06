# Design Principles

## Opt in, never take over silently

Built-in configuration, logging bridges, HTTP clients, FastAPI integration, and Uvicorn startup are available only when the caller selects the corresponding preset or plugin.

## Dependency injection before global state

Existing applications can inject configuration providers, event sinks, state stores, TLS providers, HTTP clients, connectors, and protocol services. Library mode does not configure the root logger or parse process arguments automatically.

## Protocols belong in the SDK

Agent Runtime must not duplicate OAuth, JOSE, JWT, JWK, DPoP, RFC, or protocol-validation logic. It depends on SDK-composed services and adapts them to application flows.

## Authoritative input is preserved

Agent Cards, Protected Resource Metadata, and A2UI documents are copied defensively but not destructively normalized. Unknown extensions remain intact.

## OAuth scopes are opaque

Scope strings are exact and case-sensitive. The runtime does not translate `:` to `.`, modify case, or add provider scopes to a global allowlist.

## One security boundary for every transport


## Runtime lifecycle is explicit

Initialization and shutdown are visible operations. Resources are closed in reverse dependency order. Required failures roll back prior startup.

## Operational concerns are modular

Health, metrics, telemetry, scheduling, retry, and state are ports or plugins. Process-local defaults are available, but distributed implementations can be injected.

## Documentation distinguishes implementation from roadmap

Only current behavior is documented as supported. Future capabilities appear in the [roadmap](../reference/roadmap.md).
