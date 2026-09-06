# Agent Nebula Ecosystem Engineering Contract

This file is authoritative for all human and AI-assisted changes in `agent-nebula-sdk`, `agent-runtime`, and `agent-studio`. Read it before modifying architecture, configuration, plugins, applications, agents, security, transport, lifecycle, or generated runtime files.

## 1. Repository ownership

### agent-nebula-sdk

Owns all standards, protocols, cryptography, and security behavior. This includes OAuth, RFC 6749, RFC 7523, RFC 7591, RFC 7592, RFC 7638, RFC 7662, RFC 8707, RFC 9068, RFC 9449, JOSE, JWT, JWS, JWK, JWKS, DPoP, private_key_jwt, API-key onboarding semantics, software statements, initial access tokens, protected-resource metadata validation, PKI, CSR handling, certificate validation, and trust-chain verification.

The SDK contains no application business logic, no FastAPI application composition, and no product-specific configuration.

### agent-runtime

Owns reusable application capabilities built on the SDK. Runtime plugins are complete functionality blocks, not thin registration wrappers. Runtime owns configuration models and parsing, official A2A SDK integration, path ownership, TLS, HTTP clients, Nebula connectivity, OAuth-client composition, protected-resource validation composition, discovery, onboarding, state, retry behavior, metrics, telemetry, health, server startup, PRE_SERVER and POST_SERVER phases, shutdown, and cleanup.

Runtime may import `agent_nebula_sdk`. Runtime must not duplicate SDK protocol algorithms.

### agent-studio

Owns business logic only: domain services, repositories for domain data, fixtures, handlers, business workflows, Browser Engine behavior, sessions, application HTTP contracts, public Agent Card business metadata, A2UI business surfaces, examples, tutorials, and user-facing documentation.

Studio applications select Runtime plugins and consume Runtime public services. Runtime owns reusable A2UI session infrastructure; Studio owns only browser-facing projections and orchestration decisions. Studio must not import `agent_nebula_sdk` directly and must not construct Runtime infrastructure.

### agent-genesis

Legacy behavioral reference only. Use it to understand business workflows. Never copy its configuration, startup, transport, OAuth, security, lifecycle, or composition structure into Runtime or Studio.

## 2. Required application composition

Every Runtime-based application follows this flow:

1. Agent Runtime loads and validates all `runtime.*` configuration.
2. Agent Runtime resolves runtime-owned and product-shared paths.
3. `RuntimeApplicationBuilder` constructs common infrastructure.
4. Enabled role plugins construct their SDK-backed capabilities.
5. Agent Studio constructs business services and application metadata only.
6. Agent Runtime attaches plugins to FastAPI.
7. Agent Runtime owns HTTPS server startup, lifecycle phases, and shutdown.

Provider and orchestrator applications may enable different plugins, but they must use the same configuration loader, builder, lifecycle, transport, and resource-ownership model.

## 3. Role-specific plugin composition

A provider commonly enables onboarding, protected resource, skills, Agent Card, protected-resource metadata, health, REST, A2A, A2UI, and metrics.

An orchestrator commonly enables onboarding, OAuth client, discovery, Agent Card, health, metrics, and telemetry. Its Browser API remains application business functionality.

A dual-role application may enable both OAuth-client and protected-resource capabilities.

Role profiles are convenience defaults only. Explicit plugin configuration remains authoritative. Builders must construct only enabled capabilities. Disabled capabilities must not require credentials, settings, transports, or services.

## 4. Plugin completeness requirements

A Runtime plugin or Runtime-owned capability must include:

- typed configuration;
- configuration validation;
- dependency construction;
- SDK adapter construction where required;
- lifecycle phase behavior;
- service registration in `RuntimeContext` or Runtime services;
- retry and failure policy;
- deterministic cleanup;
- structured events without secrets;
- unit tests and negative tests;
- public documentation and an application example.

A plugin must not require Agent Studio to construct SDK facades, validators, transports, caches, replay stores, SSL contexts, raw HTTP clients, or Nebula connectors.

## 5. Configuration contract

Agent Runtime exclusively owns and parses:

- `[runtime.application]`
- `[runtime.server]`
- `[runtime.nebula]`
- `[runtime.state]`
- `[runtime.logging]`
- `[runtime.plugins]`
- `[runtime.onboarding]`
- `[runtime.oauth_client]`
- `[runtime.protected_resource]`
- future `runtime.*` sections

Agent Studio parses only application sections such as `[parking]`, `[browser]`, `[sessions]`, and `[ui]`.

One shared generator renders Runtime sections for every application. Application contributors may append business sections only. Do not create application-specific Runtime renderers.

## 6. Path and secret ownership

`product_root` is the external Agent Studio installation root.

Shared resources remain under the product root:

- `certs/trust/trust-bundle.pem`
- shared onboarding API keys;
- shared OAuth identity keys when intentionally product-scoped;
- other explicitly shared credentials.

Each application has a separate `runtime_root`:

- `runtime/common-orchestrator`
- `runtime/stx-metro-parking-1`
- `runtime/fleet-control`
- future application runtime roots.

Application-owned resources remain under that application runtime root:

- service certificate, private key, and CSR;
- state;
- logs;
- generated configuration;
- application fixtures and generated UI configuration where applicable.

Do not copy shared trust or shared secrets into application runtime directories. Never log secret contents. Generated browser configuration must never contain credentials.

## 7. Forbidden Agent Studio dependencies

Studio source must not import or construct:

- `agent_nebula_sdk`;
- `ssl.SSLContext` or `ssl.create_default_context`;
- raw `httpx.AsyncClient` infrastructure clients;
- `RestNebulaConnector`;
- `RuntimeContext`;
- `JsonFileStateStore` for Runtime state;
- `OAuthClientFacade`, `OAuthClientService`, token transports, token caches, client-assertion builders, or DPoP builders;
- JWT, JWKS, RFC 9068, RFC 9449, audience, replay, or protected-resource validators;
- `ProtectedResourceService` protocol composition;
- `UvicornRuntimeServer` or Runtime lifecycle phases;
- parsing or mapping of `runtime.*` sections.

Studio may import Runtime public plugin interfaces, Runtime service interfaces, Runtime business-facing adapters, metadata providers, and the Runtime application builder.

## 8. Application-owned responsibilities

STX Metro owns parking fixtures, parking entities, parking repository/service logic, parking skills, handlers, Agent Card business metadata, and parking A2UI surfaces.

Common Orchestrator owns Browser Engine decisions, provider selection workflow, Browser API projections, orchestration decisions, and UI-facing business responses. Agent Runtime owns session state, persistence, navigation, synchronized data, action history, and task/context tracking.

Future travel, retail, finance, airline, hotel, and CloudOps applications follow the same rule.

## 9. Lifecycle contract

Runtime starts publishable HTTPS endpoints during PRE_SERVER, then starts the listener, then executes POST_SERVER onboarding, registration, heartbeat, and synchronization. Applications must not manually invoke lifecycle phases.

Runtime owns cleanup of all transports, caches, replay stores, state services, metrics/telemetry resources, and plugin-owned dependencies. Cleanup must be deterministic and idempotent.

## 10. Security requirements

Fail closed on invalid configuration, TLS verification, tokens, DPoP proofs, audience, scopes, replay, issuer, algorithms, or metadata. Do not weaken validation to make an application start. Fix ownership or configuration at the source.

OAuth scopes are opaque and resource-specific. Protected-resource audience must match the configured resource exactly. Agent Card and Protected Resource Metadata are authoritative public documents and must not be silently rewritten by applications.

## 11. Coding standards

Use production-quality object-oriented design, focused modules, complete typing, public docstrings, structured logging, configuration-driven behavior, external runtime/configuration/secrets, strict TLS, deterministic resource ownership, and comprehensive tests.

Every new file requires a module docstring. Every public class and public method requires a meaningful docstring. Major implementation blocks require comments explaining ownership and invariants, not line-by-line narration.

Routes remain thin. Repositories remain persistence-only. Application services own transactions and business workflows. Protocol logic remains in the SDK. Reusable composition remains in Runtime.

## 12. Required tests and gates

Every change must include focused unit tests, negative tests, lifecycle tests, configuration tests, and repository-boundary tests where applicable.

Studio boundary tests must scan source paths and fail on forbidden imports or constructors. Runtime tests must verify plugin-conditional construction, path containment, cleanup, retry behavior, and disabled-plugin behavior.

Before release, run full tests in both repositories and validate at least one provider plus one OAuth-client/orchestrator end to end.

## 13. Extension checklist

Before adding a new plugin, application, or agent, answer:

1. Is this protocol/security behavior? Put it in the SDK.
2. Is this reusable application capability or infrastructure? Put it in Runtime as a complete plugin/capability.
3. Is this domain/business behavior? Put it in Studio.
4. Which plugin settings enable it?
5. What resources does it own and close?
6. Which paths are application-owned versus product-shared?
7. What negative tests prove fail-closed behavior?
8. Does Studio remain free of SDK and infrastructure construction?

Any deviation requires explicit architectural approval and documentation before implementation.

## 14. Checkpoint 11.5 A2UI session ownership

A2UI session infrastructure is owned by Agent Runtime. Runtime owns persistent session snapshots, surface stacks, navigation, synchronized data models, renderer action records, task/context references, participant Agents, resume, and cleanup. Agent Studio must consume `A2UISessionService` through `RuntimeApplicationServices`; it must not implement a parallel session state machine or persistence layer. Common Orchestrator remains domain-neutral and may coordinate multiple Agents only through discovered metadata, Runtime services, and external A2UI catalogs.
