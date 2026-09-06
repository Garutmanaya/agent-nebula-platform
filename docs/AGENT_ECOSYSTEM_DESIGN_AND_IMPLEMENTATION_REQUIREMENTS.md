# Agent Nebula Ecosystem Design and Implementation Requirements

## 1. Status and authority

This document is the authoritative implementation contract for `agent-nebula-sdk`, `agent-runtime`, `agent-studio`, reference applications, and future third-party Runtime applications. New checkpoints, plugins, agents, applications, and refactors must comply with it. Existing code that conflicts with this document is migration input, not an architectural precedent.

## 2. Repository ownership

### 2.1 agent-nebula-sdk

The SDK is the only owner of standards and protocol/security implementations. It contains no application business logic and no Agent Studio-specific behavior.

It owns OAuth and related RFC behavior, JOSE, JWT, JWS, JWK, JWKS, thumbprints, DPoP, private_key_jwt, dynamic registration, protected-resource validation, A2A protocol structures, discovery protocol structures, Agent Card validation, Protected Resource Metadata validation, PKI, CSR processing, certificate validation, and trust-chain verification.

No Runtime, Studio, or third-party application may reimplement these algorithms or construct alternative protocol semantics.

### 2.2 agent-runtime

Runtime converts SDK capabilities into reusable application functionality blocks. Runtime owns configuration, dependency composition, lifecycle, transports, resource ownership, retry, state, observability, server integration, and plugin APIs.

A Runtime plugin is complete only when it owns or obtains all reusable dependencies required for its capability, registers a stable public service, participates in lifecycle phases, reports health/readiness when applicable, and closes resources it created. A plugin must not force Agent Studio to construct SDK facades, validators, proof builders, transports, caches, replay stores, connectors, or RuntimeContext objects.

### 2.3 agent-studio

Studio contains business logic, application metadata, fixtures, tutorials, business workflows, application APIs, business A2UI surfaces, and reference implementations. Studio must not implement or assemble protocols, security, Runtime infrastructure, or Runtime configuration parsing.

Studio applications select Runtime plugins, provide business handlers and metadata, and consume public Runtime services. Agent Studio must not import `agent_nebula_sdk` directly.

### 2.4 Agent Genesis

Agent Genesis is legacy behavioral reference material only. It may be consulted for domain behavior and workflows. Its configuration, startup, transports, security composition, lifecycle, and application composition must not be copied.

## 3. Mandatory layering

The dependency direction is:

```text
agent-nebula-sdk
        ↓
agent-runtime
        ↓
agent-studio and third-party applications
        ↓
business services and reference applications
```

Reverse dependencies are prohibited. Runtime must not depend on Studio. SDK must not depend on Runtime or Studio.

## 4. Runtime plugin contract

Every plugin must have a stable identifier, explicit settings, declared dependencies, deterministic initialization and shutdown, structured non-secret events, health/readiness behavior where meaningful, complete typing, public docstrings, and focused tests.

Plugins may use SDK implementations internally, but must expose Runtime-facing service interfaces. Applications consume those interfaces instead of SDK objects.

Required reusable capabilities include:

- lifecycle and server phases;
- HTTPS and verified outbound HTTP;
- Nebula connector;
- onboarding;
- discovery;
- OAuth client and private_key_jwt;
- DPoP-bound token acquisition and invocation support;
- protected-resource/provider validation;
- Agent Card publication;
- Protected Resource Metadata publication;
- skills;
- REST, A2A, and A2UI server adapters;
- A2A client capability;
- state store;
- health, metrics, telemetry, retry, and scheduling.

## 5. Role-based composition

Roles select plugins; roles do not create alternate infrastructure stacks.

### Provider profile

A provider normally enables onboarding, protected resource, protected-resource metadata, skills, Agent Card, health, REST and/or A2A, optional A2UI, metrics, and telemetry.

Runtime must construct token validation, DPoP validation, JWKS resolution/cache, replay protection, audience validation, authorization service, transport ownership, and cleanup from SDK implementations.

The provider application supplies domain services, skills, required opaque scopes, resource identity, metadata, Agent Card business metadata, and business response surfaces.

### OAuth client/orchestrator profile

An orchestrator normally enables onboarding, discovery, OAuth client, A2A client or secure invocation support, Agent Card, health, metrics, and telemetry.

Runtime must construct OAuth identity, private_key_jwt, DPoP proofs, token transport/cache, verified provider HTTP transport, Nebula connectivity, and cleanup.

The application supplies orchestration workflows, sessions, business APIs, provider-selection logic, and UI contracts.

### Dual-role profile

A dual-role application may enable both client and provider capabilities. Runtime must compose both from the same common infrastructure without duplicated transports, state, lifecycle, or configuration parsing.

Role profiles are validated defaults. Explicit plugin overrides remain supported, but invalid combinations must fail during configuration validation.

## 6. Configuration ownership

Runtime owns every `runtime.*` section and provides the only parser/model for those sections. Studio may parse only application-specific sections such as `browser`, `sessions`, `ui`, `parking`, `fixtures`, or other domain namespaces.

Role-specific settings are optional and required only when their plugin is enabled. Disabled plugins must not require credentials or construct services.

Configuration generation must use one shared Runtime renderer/model. Application-specific generators may contribute only application sections and metadata; they must not generate alternate TLS, Nebula, OAuth, onboarding, state, or plugin schemas.

No hardcoded URLs, filesystem paths, credentials, issuers, resources, algorithms, ports, or scopes are allowed in application code.

## 7. Filesystem and secret ownership

Each application has an independent runtime root:

```text
$PRODUCT_HOME/runtime/<application-id>/
    config/
    certs/service.crt
    certs/service.key
    certs/service.csr
    data/state/
    logs/
    fixtures/ or ui/ when required
```

The product root owns shared resources:

```text
$PRODUCT_HOME/certs/trust/trust-bundle.pem
$PRODUCT_HOME/secrets/
```

Application certificates, state, logs, and generated files must remain inside the application runtime root. Shared trust bundles and shared credentials must remain under the product root and must not be copied into individual application runtime trees.

RuntimePathResolver is the authoritative containment mechanism. Application-owned paths resolve only beneath `runtime_root`. Shared paths resolve beneath `product_root` or, when intentionally app-specific, `runtime_root`. Path traversal outside managed roots must fail closed.

Secret contents must never be logged, returned in exceptions, embedded in generated public configuration, or copied into UI assets.

## 8. Lifecycle and resource ownership

Runtime owns PRE_SERVER, listener startup integration, POST_SERVER, readiness, shutdown, and reverse-order cleanup. Applications must not call Runtime phases manually or create separate lifecycle stacks.

PRE_SERVER publishes locally available endpoints and metadata needed before onboarding. POST_SERVER performs onboarding, registration resolution, heartbeat, synchronization, and other operations requiring a reachable HTTPS endpoint.

Every transport, cache, replay store, connector, task, and background service must have one explicit owner. Runtime closes resources it creates. Applications close only business resources they create.

## 9. Agent Studio restrictions

Agent Studio and Studio applications must not directly construct or import:

- `agent_nebula_sdk` protocol/security classes;
- `ssl.SSLContext` or `ssl.create_default_context`;
- raw `httpx.AsyncClient` infrastructure clients;
- Nebula connectors;
- OAuth facades/services/transports/caches;
- JWT, JWKS, DPoP, replay, or protected-resource validators;
- `RuntimeContext`;
- Runtime state-store implementations;
- Runtime servers or lifecycle phase calls;
- parsers for `runtime.*` configuration;
- plugin dependency graphs.

Repository-boundary tests must enforce these restrictions.

## 10. Application composition pattern

A Runtime-based application should perform only these steps:

1. Ask Runtime to load and validate `runtime.*` settings.
2. Ask RuntimeBuilder to construct common and enabled role-specific plugins/services.
3. Load application-specific settings through the application package.
4. Construct business repositories, services, handlers, skills, metadata providers, and routes.
5. Supply business components to Runtime attachment/composition.
6. Start the Runtime-owned application/server lifecycle.

Provider and orchestrator applications must use this same flow. Their only structural difference is plugin selection and business components.

## 11. Public API and dependency-injection rules

Runtime public services must be exposed through typed interfaces or service containers. Applications must not reach into private plugin fields. Plugins must register stable service identifiers and document availability by lifecycle phase.

Business components may depend on Runtime interfaces such as discovery, secure invocation, OAuth token provider, protected-resource authorization, state abstraction, metrics, or events. They must not depend on SDK internals.

## 12. Security rules

TLS verification is mandatory. Plain HTTP is forbidden except explicitly documented loopback-only test fixtures. Trust bundles must be explicit. mTLS certificate and key configuration must be paired. Private keys and API keys must use restrictive permissions.

OAuth scopes are opaque, case-sensitive, and resource-specific. Runtime and Studio must not normalize, infer, rename, merge, or reuse scopes across resources.

Agent Card and Protected Resource Metadata are authoritative documents. Runtime publishes application-provided metadata but SDK validation determines protocol correctness.

## 13. Testing requirements

Every checkpoint must include:

- unit tests for settings, path containment, plugin factories, lifecycle, and cleanup;
- contract tests for public APIs and repository boundaries;
- integration tests for enabled/disabled plugin combinations;
- provider and OAuth-client role tests;
- negative tests for missing settings, invalid paths, missing secrets, TLS failures, token/DPoP failures, and resource cleanup;
- regression tests for existing business APIs and UI contracts.

A disabled plugin must not require its settings or credentials. An enabled plugin with missing dependencies must fail before serving business traffic.

## 14. Documentation and coding standards

Code must be production-quality, object-oriented where ownership/lifecycle benefits, plugin-based, configuration-driven, fully typed, and organized into focused modules. Every file, public class, and public method requires a useful docstring. Major implementation blocks require comments explaining ownership or security decisions rather than restating syntax.

Each checkpoint must update architecture documentation, configuration examples, migration notes, public API references, and tests. Temporary compatibility paths must be explicitly marked with removal criteria.

## 15. Extension checklist

Before adding a plugin or application, answer:

1. Is any part a protocol/security implementation? It belongs in SDK.
2. Is it reusable infrastructure or capability composition? It belongs in Runtime.
3. Is it domain behavior, workflow, metadata, fixture, or UI/business contract? It belongs in Studio/application code.
4. Does Runtime already expose the capability? Reuse it; do not duplicate it.
5. Does the plugin own construction and cleanup of reusable dependencies?
6. Are settings optional and validated based on enablement?
7. Are all paths assigned to runtime-root or product-root ownership?
8. Are repository boundaries enforced by tests?

## 16. Completion criterion

The architecture is compliant when deleting all protocol/security construction, Runtime-specific parsing, TLS/HTTP/Nebula composition, state/lifecycle wiring, and SDK imports from Agent Studio does not remove business functionality. Studio applications must remain functional by selecting Runtime plugins and supplying business components only.
