# Runtime Plugin and Studio Application Implementation Requirements

## Purpose

This document is the implementation checklist for every new Runtime plugin and every Agent Studio or third-party Runtime application. It supplements the ecosystem design contract and must be reviewed during code generation and review.

## New Runtime plugin requirements

A new plugin must define its reusable capability boundary, public service interface, strict settings model, enablement dependencies, initialization phase, health/readiness behavior, structured events, resource ownership, shutdown order, and tests. SDK protocol objects must be constructed inside Runtime factories or plugin composition services, never in Studio.

Plugin settings must be optional at the aggregate application level and required only when the plugin is enabled. Disabled plugins must not load secrets, open transports, create caches, initialize replay stores, or require unrelated configuration.

A plugin that creates a transport, background task, cache with resources, file watcher, connector, or server owns its cleanup. Shared transports must have one Runtime owner and may be injected into multiple services without duplicate close operations.

Public plugin services must be typed and stable. Business applications consume Runtime interfaces and may not reach into SDK objects or private plugin members.

## New Studio application requirements

A Studio application may define domain settings, repositories, services, workflows, handlers, skills, application metadata, fixtures, routes, and business UI/A2UI contracts. It selects Runtime plugins and supplies business components through public Runtime composition APIs.

A Studio application must not parse `runtime.*` sections, create TLS contexts, instantiate infrastructure HTTP clients, read Runtime credentials, construct Nebula connectors, construct RuntimeContext, build OAuth/DPoP/JWT/JWKS services, manage Runtime state storage, call lifecycle phases, or own the Runtime server.

Every application must have a unique `$AGENT_STUDIO_HOME/runtime/<application-id>` root. Service certificates and application state stay under that root. Shared trust and shared credentials stay under `$AGENT_STUDIO_HOME/certs/trust` and `$AGENT_STUDIO_HOME/secrets`.

## Required review gates

Before merge, verify:

1. Repository ownership is correct.
2. No protocol/security implementation exists outside SDK.
3. No reusable infrastructure composition exists in Studio.
4. Plugin enablement controls settings validation and service construction.
5. Paths use RuntimePathResolver ownership rules.
6. Secrets are file-backed, external, permission-restricted, and never logged.
7. Lifecycle and cleanup are deterministic.
8. Provider, OAuth-client, disabled-plugin, failure, and restart tests exist.
9. Studio boundary tests reject direct SDK and infrastructure imports.
10. Architecture and configuration documentation is updated.

## Role examples

A provider selects provider/protected-resource, onboarding, Agent Card, protected-resource metadata, skills, server transports, health, metrics, and optional A2UI. It adds only domain services and handlers.

An orchestrator selects onboarding, discovery, OAuth client, secure invocation/A2A client, Agent Card, health, metrics, and telemetry. It adds only orchestration workflows, sessions, business APIs, and UI contracts.

A dual-role application selects both capability sets but still uses one Runtime context, one lifecycle, one state framework, and Runtime-owned transports.

## Checkpoint 11.5 A2UI session requirement

Interactive A2UI session infrastructure is a complete Agent Runtime capability. Runtime owns session persistence, surface transitions, back/forward navigation, synchronized data-model state, renderer action records, A2A task/context references, participant Agents, and resume/close lifecycle. Agent Studio applications consume the Runtime service and may only project it into business-facing APIs and user interfaces.
