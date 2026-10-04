# A2A SDK Integration Requirements

## Purpose

Agent Nebula extends the official `a2a-sdk`; it does not define a second A2A API.
This document is the ownership contract for Platform and SecureAgent integrations.

## Requirements

1. **The official SDK is authoritative.** `a2a-sdk` owns AgentCard models, messages,
   tasks, artifacts, streaming, push notifications, transports, client operations,
   request handling, AgentExecutor, and other standard A2A behavior.
2. **Platform is the single SDK integration boundary.** Platform constructs and
   configures official SDK clients and servers. SecureAgent does not independently
   implement A2A protocol behavior.
3. **Do not mirror SDK operations.** Platform and SecureAgent must not add wrapper
   methods for `Client` operations merely to rename, normalize, or hide them. A
   configured native `a2a.client.Client` is returned when native A2A access is
   required.
4. **Preserve official SDK models.** Native A2A APIs return official models. Do not
   translate AgentCard, Task, Message, StreamResponse, or other SDK models into a
   parallel Nebula model or dictionary representation.
5. **Nebula additions must add distinct value.** New Nebula APIs are limited to
   configuration-driven composition, security implementation/configuration,
   Registry/discovery, lifecycle conveniences, and explicitly documented Nebula
   A2A extensions.
6. **Use official extension points.** Client credential injection uses
   `ClientCallInterceptor`. Server execution uses `AgentExecutor`/request-handler
   extension points. Nebula extensions use A2A extension metadata/context rather
   than changes to official wire models.
7. **Security remains external to A2A semantics.** Agent Nebula may acquire OAuth,
   DPoP, API-key, OIDC, HTTP-auth, or mTLS credentials, but applies them through
   SDK-supported integration points. Standard A2A request execution remains SDK
   owned.
8. **Configuration is an additive convenience.** SecureAgent may construct skills,
   AgentCards, clients, and servers from configuration/decorators because this
   reduces setup; generated objects must still map to official SDK interfaces.
9. **Nebula-specific behavior must be explicit.** Source comments must use
   `AGENT NEBULA INTEGRATION`, `AGENT NEBULA SECURITY`, or `AGENT NEBULA EXTENSION`
   where ownership could otherwise be ambiguous, and explain why the addition is
   outside the standard SDK.
10. **Prefer composition and pluggability.** Configuration loaders, credential
    providers, security resolvers, extension contributors, stores, and other
    replaceable concerns should have focused interfaces and be injected/composed
    rather than embedded in protocol operations.
11. **SDK upgrades stay localized.** A compatible `a2a-sdk` upgrade should normally
    affect Platform integration/composition only. A newly added SDK client operation
    must become usable through the returned native client without a matching
    Platform/SecureAgent API change.
12. **Convenience APIs are not the native A2A API.** Existing Nebula conveniences
    such as Registry `discover()` or discovered-provider skill selection may remain,
    but documentation and comments must identify them as Nebula functionality.
13. **No feature expansion during boundary refactoring.** Client/server refactors
    preserve current behavior. New protocol features and examples are separate work.
14. **Apply the same ownership model to A2UI.** Standard A2UI behavior remains owned
    by its standard implementation/SDK; Nebula adds only configuration, security,
    lifecycle, and explicit extensions.

## Client layering

```text
Application
    |
    +-- SecureAgent configuration / Registry convenience
    |
    v
Agent Nebula Platform
    +-- load client configuration
    +-- configure TLS
    +-- install security ClientCallInterceptor
    +-- install explicit Nebula extension integration
    |
    v
a2a-sdk ClientFactory -> a2a.client.Client
                         -> native SDK operations
```

`SecureAgent.a2a_client()` is a configuration entry point, not an A2A wrapper. It
returns the native SDK client. The caller uses and closes that client according to
`a2a-sdk` semantics; `SecureAgent.close()` releases Platform-owned credential
provider resources.

## API ownership test

Before adding an API, ask: **Would this operation still exist if Agent Nebula
configuration, security, Registry, and extensions were removed?** If yes, it belongs
to the standard SDK and must not be duplicated by SecureAgent.

## Server layering

```text
SecureAgent configuration / @agent.skill
    |
    v
Agent Nebula Platform
    +-- construct official AgentCard from configuration
    +-- adapt configured skills through AgentExecutor
    +-- authenticate through ServerCallContextBuilder
    +-- configure TLS / advertised interfaces
    |
    v
a2a-sdk
    +-- DefaultRequestHandler
    +-- TaskStore
    +-- JSON-RPC / HTTP+JSON / gRPC routes
    +-- task, streaming, push-notification, and protocol semantics
```

`A2AAgentExecutor` is an integration adapter, not a replacement A2A execution API.
It maps SecureAgent's configuration-driven skills onto the official `AgentExecutor`
extension point. Server HTTP authentication similarly uses the official
`ServerCallContextBuilder` extension point; Platform must not rewrite or wrap
SDK-generated protocol endpoints merely to enforce Nebula security.

The public Agent Card route remains outside authenticated protocol-call context
construction. Security requirements advertised by that card are enforced when the
SDK builds the call context for A2A protocol operations.

## Server security composition

`A2AServerSecurityFactory` is the single Platform composition boundary for
server-side A2A authentication. The official Agent Card remains authoritative for
`securitySchemes` and `securityRequirements`; Agent Nebula supplies the configured
credential validators without changing A2A wire models.

OAuth2 is not a parallel server path. The factory delegates OAuth protected-resource
construction to `A2AProtectedResourceFactory`, adapts that existing service through
`A2AOAuth2ProtectedResourceAuthenticator`, and composes it into the same
`A2AServerSecurityService` used by API-key, HTTP-auth, OpenID Connect, and mTLS
adapters. Unsecured Agent Cards produce a security service whose `required` property
is false, preserving existing unsecured server behavior.

Scheme-specific authentication remains pluggable. The factory owns composition, not
credential algorithms: generic verification stays in `agent-nebula-sdk`, A2A scheme
adapters stay in Platform, and enforcement enters the official SDK server pipeline
through `A2ASecurityServerCallContextBuilder`.
