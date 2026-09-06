## Unreleased

- Step 7: removed legacy/custom A2A code; A2A 1.0 official SDK path is authoritative.
- Standardized repository Makefile developer targets.

## 0.10.1 — Checkpoint 11.4.2 Stage 2

## A2A 1.0 Step 4

- Added dedicated `a2aclient.conf` loading with fail-closed transport and TLS validation.
- Added Runtime-owned official A2A client construction using `A2ACardResolver`, `ClientConfig`, and `ClientFactory`.
- Added verified HTTP and TLS gRPC transport construction while leaving Agent Card security negotiation to Step 5.


- Added Runtime-owned onboarding payload builders and protected OAuth/DPoP HTTP invocation.
- Added RuntimeApplication server ownership for Studio applications.
- Corrected role-profile parsing in the shared Runtime INI loader.
- Added comma-separated protected-resource algorithm parsing.
- Added authoritative AGENTS.md and CLAUDE.md engineering contracts.

# Changelog

## 0.10.0 — Checkpoint 11.4.2 Stage 1

- Added role-neutral Runtime application settings and a Runtime-owned INI loader.
- Added centralized runtime-root and product-root path ownership.
- Added optional OAuth-client and protected-resource capability settings.
- Added Runtime-owned SDK-backed provider security composition and cleanup.
- Made role service construction conditional on enabled plugins.
- Added the authoritative ecosystem design and implementation requirements.

## 0.9.3

- Added `OnboardingOAuthClientIdentity` for Runtime-owned key loading and client-ID recovery from onboarding state.
- Added public JWKS generation for caller-agent OAuth onboarding.

## Checkpoint 9.1 — Documentation

- Added a cross-linked `docs/` knowledge base covering architecture, design principles, configuration, plugins, security, runtime behavior, migration, examples, package reference, terminology, capability status, and roadmap.
- Consolidated the architectural rationale and ecosystem boundaries previously captured only in design discussions.
- Added a documentation entry point from the top-level README.

## 0.7.0

- Added typed Agent Card builders that preserve custom metadata, schemas, examples, extensions, and top-level source members.
- Added RFC 9728 Protected Resource Metadata builders validated by `agent-nebula-sdk`.
- Added cross-document validation for Agent Card skill declarations, runtime skill definitions, and protected-resource scopes.
- Added preset integration so authoritative Agent Card validation occurs during skill-plugin initialization.

## 0.6.0

- Added asynchronous A2A task lifecycle, correlation identifiers, cancellation, ordered event replay, SSE streaming, and host-approved push notification ports.
- Added task ownership enforcement for protected A2A control operations.
- Added A2A task plugin and preset composition.
- Preserved compatible immediate `/a2a` skill invocation.

## 0.5.0

- Added embedded preset composition for existing FastAPI applications.
- Added standalone preset composition for Agent Studio and new agents.
- Added strict INI settings for runtime root, HTTPS listener, Agent Nebula TLS,
  local state, and isolated console event logging.
- Added preset-owned resource shutdown and Uvicorn startup.
- Marked the presets capability as available.

## 0.4.0

- Added declarative A2UI v0.9.1 surface and message contracts.
- Added approved-component catalog and executable-content validation.
- Added A2A-compatible `application/a2ui+json` DataPart serialization.
- Added A2UI action bindings and OAuth/DPoP-protected action dispatch.
- Added optional FastAPI A2UI action endpoint.
- Added A2UI artifacts to skill results.
- Marked the A2UI runtime capability available.

## 0.3.0

- Added authoritative Agent Card and RFC 9728 metadata providers.
- Added typed skill declarations, registry, and sync/async dispatch.
- Added exact scope validation between skills and protected-resource metadata.
- Added shared REST and A2A method adapters backed by one authorization boundary.
- Added opt-in FastAPI route attachment and lifespan integration.
- Added health and readiness provider contracts and endpoints.

## 0.2.0

- Added OAuth client-credentials orchestration using `agent-nebula-sdk` facades.
- Added HTTPX token transport and in-memory token cache.
- Added DPoP-protected outbound request construction.
- Added protected-resource authentication and exact-scope authorization.
- Added runtime service registry and OAuth plugins.
- Added capability roadmap and explicit unimplemented-capability errors.
- Added plugin lifecycle status tracking.
- Added documented package placeholders for all planned runtime modules.

## 0.1.0

- Initial plugin runtime, Agent Nebula connector, onboarding, discovery, lifecycle, TLS, state, configuration, and event abstractions.


## 0.8.0

- Added deterministic configuration precedence: built-ins, external INI, environment, then CLI overrides.
- Added `AGENT_RUNTIME_HOME` and conventional external configuration/secret paths.
- Added strict file-backed secret handling and root-escape protection.
- Added explicit plugin enable, disable, and automatic composition settings.
- Added fail-closed validation when enabled plugins lack required components.

## 0.9.0

- Added plugin-level health and readiness aggregation.
- Added counters, gauges, timing summaries, and JSON metrics exposure.
- Added structured telemetry events with console and JSON-lines sink adapters.
- Added startup, shutdown, one-shot, and interval scheduler jobs.
- Added bounded retry policies with fixed, linear, exponential, and jittered delays.
- Added plugin lifecycle hooks and graceful reverse-order background shutdown.

## 0.9.1

- Added explicit pre-server and post-server plugin lifecycle phases.
- Deferred Agent Nebula onboarding until the HTTPS listener reports readiness.
- Added a Uvicorn runtime server that owns the listener-ready boundary.
- Preserved `initialize()` as a compatibility API for non-server integrations and tests.

## 0.9.2 — Checkpoint 11.1

- Stabilized the A2UI renderer-facing public contract.
- Added explicit runtime capabilities and renderer negotiation models/endpoints.
- Added configurable supported-version, preferred-version, and catalog policies.
- Added mixed-version, unresolved-reference, unapproved-catalog, and unregistered-action validation.
- Added startup validation that every A2UI action binding targets a registered skill.
- Preserved secure action dispatch through the existing OAuth, DPoP, and exact-scope boundary.

## A2A 1.0 Step 2

- Derive active A2A server transports from the official Agent Card `supported_interfaces`.
- Mount official `a2a-python` JSON-RPC, HTTP+JSON, and Agent Card routes on FastAPI.
- Add optional official gRPC server integration through the `a2a-grpc` extra.
- Fail startup for unsupported bindings or protocol versions instead of advertising unavailable interfaces.
- Add preset injection points for the official `AgentCard` and `RequestHandler` while retaining the legacy path until Step 7 cleanup.

### A2A 1.0 Step 3 - server security enforcement
- Added transport-neutral A2A security requirement resolution with official OR-of-AND semantics.
- Added fail-closed startup validation for advertised security scheme families.
- Protected official JSON-RPC and HTTP+JSON routes while keeping Agent Card discovery public.
- Added an OAuth2 adapter over the existing SDK-backed DPoP protected-resource service.
- Added pluggable authenticators keyed by official SecurityScheme oneof type, never arbitrary scheme names.
- Secured gRPC now fails closed until a transport-specific gRPC authentication adapter is configured.

## A2A 1.0 Step 6

- Composed Step 5 security providers automatically in `A2AClientServiceFactory`.
- Added Runtime-owned standard `SendMessageRequest` construction/response normalization for thin higher-level facades.

## Unreleased

- Added the Agent Nebula A2A skill-selection extension for deterministic client-selected `AgentSkill.id` dispatch without changing official A2A wire models.
- Added multi-skill A2A executor composition while preserving single-skill compatibility.
- Added skill-aware client security resolution so selected skill security requirements can drive least-privilege credential acquisition.
