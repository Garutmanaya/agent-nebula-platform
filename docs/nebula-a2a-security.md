# Agent Nebula A2A Security Implementation

## Scope

This document describes Agent Nebula server-side A2A security for A2A protocol 1.0 using `a2a-sdk==1.1.5`. The design deliberately keeps protocol parsing, transport dispatch, task lifecycle, streaming, and `AgentExecutor` invocation inside the official SDK.

Agent Nebula adds only the security mechanisms that A2A advertises but does not itself implement: credential validation, AgentCard requirement enforcement, and authorization of the AgentSkill selected by the Agent Nebula skill-selection extension.

## A2A security contract

The Agent Card contains three related security declarations:

- `securitySchemes`: named security mechanisms available to the agent, such as API key, HTTP authentication, OAuth 2.0, OpenID Connect, or mutual TLS.
- `AgentCard.securityRequirements`: requirements for contacting the agent.
- `AgentSkill.securityRequirements`: security schemes necessary for a particular skill.

A `SecurityRequirement` can reference one or more named schemes. Agent Nebula preserves the A2A/OpenAPI OR-of-AND model: alternative requirement objects are OR choices; schemes within one requirement are all required. For OAuth/OIDC, the requirement values are scopes.

The Agent Card is the authoritative public security contract. Verifier secrets, private keys, client secrets, trust policy, and other private enforcement configuration remain external to the Agent Card.

## Design goals

1. Reject unauthenticated or unauthorized requests before application business logic executes.
2. Keep `AgentExecutor` free of authentication and authorization responsibilities.
3. Use one skill-authorization implementation for JSON-RPC, HTTP+JSON, and gRPC.
4. Do not parse JSON-RPC or REST payloads in Agent Nebula middleware when `a2a-sdk` already provides parsed A2A request objects.
5. Do not replace `DefaultRequestHandler`, task handling, streaming, or SDK execution semantics.
6. Keep Agent Nebula's skill-selection extension as the only Nebula-specific input needed to identify the selected skill.

## Server flow

```text
Incoming A2A request
        |
        v
A2A transport owned by a2a-sdk
(JSON-RPC / HTTP+JSON / gRPC)
        |
        v
A2ASecurityServerCallContextBuilder
        |
        +-- build A2ASecurityRequest
        +-- validate credentials / OAuth token / DPoP exactly once
        +-- enforce AgentCard.securityRequirements
        +-- store trusted principals/claims/scopes in ServerCallContext.state
        |
        v
parsed A2A request + authenticated ServerCallContext
        |
        v
A2AAuthorizedRequestHandler
        |
        +-- inspect parsed SendMessageRequest metadata
        +-- resolve Agent Nebula selected skill
        +-- locate AgentSkill.securityRequirements
        +-- authorize selected skill from cached authenticated context
        +-- NO token validation / NO DPoP validation / NO replay-cache access
        +-- reject before SDK execution if unauthorized
        |
        v
DefaultRequestHandler
        |
        v
AgentExecutor
        |
        v
application business logic
```

## Agent-level authentication and authorization

`A2ASecurityServerCallContextBuilder` is the HTTP `ServerCallContextBuilder` integration supplied to the official SDK route factories. It converts transport credential material into `A2ASecurityRequest` and delegates enforcement to `A2AServerSecurityService`.

When `AgentCard.securityRequirements` is present, `A2AServerSecurityService.authenticate()` evaluates the advertised requirements against configured Agent Nebula authenticators. Successful principals are stored in `ServerCallContext.state`. When an AgentCard-level OAuth requirement exists, this is the point at which the access token and DPoP proof are cryptographically validated. If OAuth appears only at skill level, validation is deferred until that skill requirement is known. The trusted OAuth protected-resource result already contains the authenticated subject, client identity, token claims, and granted scopes needed by later policy checks.

Raw credential material is retained only in request-local `ServerCallContext.state` so a mechanism introduced solely by a skill can be authenticated once when that skill is resolved. Already-authenticated schemes are never re-validated. RFC 9449 requires a unique DPoP proof for each HTTP request and permits servers to retain a proof's `jti` for replay detection. Re-validating the same proof while processing the same A2A request can therefore be correctly rejected as a replay. Disabling replay detection is not an acceptable workaround.

This stage occurs before `RequestHandler` and therefore before `DefaultRequestHandler` or `AgentExecutor`.

## Skill-level authorization

The selected skill cannot be reliably authorized in the HTTP context builder because the builder operates before the A2A transport has supplied the parsed `SendMessageRequest` to application request handling. The skill ID is carried by the Agent Nebula skill-selection extension metadata.

`A2AAuthorizedRequestHandler` therefore wraps the native SDK `RequestHandler`.

For both `on_message_send()` and `on_message_send_stream()` it:

1. receives the SDK-parsed `SendMessageRequest`;
2. receives the authenticated `ServerCallContext` created by the transport security layer;
3. reads the activated Agent Nebula skill-selection extension from request metadata;
4. resolves the selected `AgentSkill.id`;
5. reads the trusted principals/claims/scopes already stored in `ServerCallContext.state`;
6. evaluates that skill's `securityRequirements` through `A2AServerSecurityService`, reusing cached principals and invoking an authenticator only for a scheme not previously required by this request;
7. delegates the unchanged request and context to the native `DefaultRequestHandler` only after authorization succeeds.

This is a strict authentication/authorization separation. Authentication is a credential-validation event performed once at ingress. Authorization is a policy evaluation that may occur at both AgentCard and AgentSkill boundaries using the same authenticated result. Skill authorization must never re-validate an already-authenticated OAuth token, DPoP proof, API key, client certificate, or other request credential; it may perform the first authentication of a mechanism introduced only by the selected skill.

For a single-skill agent, absence of explicit skill-selection metadata resolves to the only advertised skill. A multi-skill agent must activate the skill-selection extension so authorization cannot accidentally be performed against the wrong skill.

Task retrieval, task cancellation, task subscription, push-notification configuration, and extended-card operations do not select a new skill. The wrapper delegates those operations directly to the native handler; their applicable agent-level security remains enforced at ingress.


## Authentication versus authorization invariant

Agent Nebula treats credential validation and policy evaluation as separate operations:

```text
HTTP request + credentials
        |
        v
A2ASecurityServerCallContextBuilder
        |  AUTHENTICATION / CREDENTIAL VALIDATION -- ONCE
        |  token signature, issuer/audience, DPoP binding, jti replay check
        v
trusted ServerCallContext.state
        |  principal + claims + granted scopes
        +-------------------------+
        |                         |
        v                         v
AgentCard policy             AgentSkill policy
        |                         |
        |                   AUTHORIZATION ONLY
        |                   no credential validation
        +------------+------------+
                     v
             DefaultRequestHandler
                     v
                AgentExecutor
```

A2A `SecurityRequirement` semantics are preserved during authorization: requirement objects are alternatives (OR), while all named schemes inside the selected requirement must be satisfied (AND). Required OAuth/OIDC scope values are checked as a subset of the trusted granted scopes produced during ingress authentication.

## Why RequestHandler instead of FastAPI middleware

FastAPI/Starlette middleware is earlier in the HTTP lifecycle, but it is the wrong abstraction for Agent Nebula skill authorization.

A middleware implementation would need to understand raw JSON-RPC request bodies, REST route shapes, extension metadata encoding, request-body replay/caching, and HTTP-specific error behavior. It would also not protect gRPC, requiring a separate gRPC implementation. That duplicates transport/protocol responsibilities already implemented by `a2a-sdk`.

The SDK's `RequestHandler` interface is explicitly transport-independent. JSON-RPC and HTTP+JSON route implementations delegate parsed requests to it, and `GrpcHandler` delegates gRPC calls to the same interface. At this boundary Agent Nebula has exactly the information it needs: a strongly typed `SendMessageRequest` plus `ServerCallContext`, while `AgentExecutor` has not yet been invoked.

Therefore the RequestHandler wrapper provides the narrowest integration point that is both pre-execution and common to all three A2A bindings.

## Why authorization is not performed in AgentExecutor

`AgentExecutor` is the application execution boundary. Putting `authorize_skill()` in `_SkillDispatcher.execute()` means unauthorized input has already crossed into the business-execution layer. It also couples application routing to security state and forces transport authentication material to be interpreted during execution.

The corrected design makes `_SkillDispatcher` responsible only for deterministic mapping from selected `AgentSkill.id` to the application's native SDK `AgentExecutor`. Security is complete before the SDK invokes it.

## SDK ownership versus Agent Nebula ownership

```text
a2a-sdk 1.1.5                     Agent Nebula
-----------------------------     ---------------------------------
AgentCard/AgentSkill models        external security configuration
SecurityRequirement models        credential/token verification
JSON-RPC parsing                   AgentCard requirement enforcement
HTTP+JSON parsing                  skill-selection extension semantics
gRPC service mapping               AgentSkill authorization
ServerCallContext                  Registry/runtime integration
RequestHandler interface
DefaultRequestHandler
Task lifecycle
streaming/event queues
AgentExecutor interface
```

Agent Nebula does not modify `a2a-sdk` and does not introduce an alternative A2A request protocol.

## Binding behavior

### JSON-RPC

`create_jsonrpc_routes()` receives the same wrapped `RequestHandler`. The SDK parses JSON-RPC and calls `on_message_send()` or `on_message_send_stream()` with typed A2A objects.

### HTTP+JSON

`create_rest_routes()` receives the same wrapped `RequestHandler`. No REST-specific Agent Nebula authorization parser is required.

### gRPC

`GrpcHandler` receives the same wrapped `RequestHandler`, so skill authorization remains at the same logical boundary. Transport authentication for secured gRPC still requires the Platform gRPC security/context adapter; the current Platform intentionally refuses to expose secured gRPC when that transport security adapter is unavailable.

## Example 07 behavior

Example 07 advertises OAuth with `agent.invoke` at both the AgentCard and each skill. One access token containing the required scope satisfies both declarations; two separate tokens are not required. The call-context security layer validates the OAuth token and DPoP proof once, records the trusted granted scopes, and enforces the AgentCard requirement. The RequestHandler then checks `agent.invoke` for the selected skill against those already-validated scopes. It does not call the OAuth/DPoP authenticator a second time.

## Example 08 behavior: skill-only security

Example 08 intentionally has no `AgentCard.securityRequirements`.  The Agent
Card only defines the OAuth scheme; each skill independently requires its own
least-privilege scope (`hello.invoke`, `echo.invoke`, or `add.invoke`).  This is
a valid A2A 1.0 configuration and must not be converted into an artificial
agent-level OAuth requirement.

The HTTP context builder therefore records the normalized request security
material but performs no authentication merely because `securitySchemes` is
present.  After the SDK parses the request, `A2AAuthorizedRequestHandler`
resolves the selected skill.  The generic requirement evaluator sees that the
skill requires OAuth, authenticates that scheme once, caches the trusted
principal, evaluates the selected skill scope, and only then delegates to
`DefaultRequestHandler`.

```text
public AgentCard + OAuth-protected skill
        |
        v
ServerCallContextBuilder
        |  no AgentCard requirement -> no authentication yet
        |  retain request-lifetime security material
        v
A2AAuthorizedRequestHandler
        |  selected skill = hello
        |  requirement = oauth(hello.invoke)
        v
SecurityRequirement evaluator
        |  OAuth principal not cached -> authenticate ONCE
        |  cache trusted OAuth principal/scopes
        |  authorize hello.invoke from trusted scopes
        v
DefaultRequestHandler -> AgentExecutor
```

## Complete Nebula A2A security model

A2A 1.0 defines the declarative contract: `securitySchemes`, optional
`AgentCard.securityRequirements`, optional `AgentSkill.securityRequirements`,
and OR-of-AND requirement semantics.  It relies on established web security
mechanisms for actual credential processing.  The official Python SDK models
those declarations and provides server context/request-handler integration
points; it does not provide a complete multi-scheme credential-validation and
policy-enforcement engine.  The behavior in this section is therefore the
**Agent Nebula A2A security implementation** layered on the official protocol
and SDK, not a replacement A2A protocol.

### Supported requirement locations

Agent and skill requirements are independent.  Nebula supports all four
combinations:

```text
Agent requirement    Skill requirement    Enforcement
-----------------    -----------------    -------------------------------
none                 none                 public request
scheme(s)            none                 authenticate/authorize at agent
none                 scheme(s)            defer authentication to skill
scheme(s)            scheme(s)            satisfy both; reuse cached auth
```

A scheme being present in `AgentCard.securitySchemes` only defines it.  It does
not by itself require authentication.

### Mixed mechanisms across agent and skill

The authenticated context is a per-request cache keyed by the **advertised
security scheme name**, not a single OAuth identity.  This permits different
mechanisms at each policy boundary.

```text
AgentCard.securityRequirements = mTLS
Skill.securityRequirements     = OAuth(payment.invoke) + API-Key

request
  |
  +-- mTLS certificate -------- authenticate once -> cache "mtls"
  |
  v
agent policy ------------------ mTLS PASS
  |
  v
selected skill
  |
  +-- OAuth token/DPoP -------- authenticate once -> cache "oauth"
  |                              authorize payment.invoke
  |
  +-- API key ----------------- authenticate once -> cache "api-key"
  |
  v
skill policy ------------------ OAuth AND API-Key PASS
  |
  v
DefaultRequestHandler -> AgentExecutor
```

If the skill later references the same mTLS or OAuth scheme, Nebula reuses the
cached principal.  It does not repeat certificate, token, API-key, OIDC, HTTP
authentication, or DPoP validation.

### OR-of-AND evaluation

A2A security requirements are evaluated exactly as advertised:

```text
securityRequirements = [
    { oauth },
    { api-key, mtls }
]

means

OAuth OR (API-Key AND mTLS)
```

Nebula tries requirement alternatives in order.  Within one alternative every
scheme must succeed.  Successful scheme authentication is cached even if a
later scheme causes that alternative to fail, so another alternative cannot
cause the same credential to be cryptographically validated again.

### Authentication is scheme validation; authorization is policy evaluation

Authenticators receive **no requirement scopes**.  Their responsibility is to
validate the credential/mechanism and return a trusted principal.  OAuth/OIDC
scope values are evaluated afterwards from trusted claims/scopes.

This separation is required for correct alternative handling.  For example:

```text
OAuth(scope-A) OR OAuth(scope-B)
```

must not validate the OAuth token/DPoP proof once for `scope-A` and then again
for `scope-B`.  Nebula validates OAuth once, caches the result, then evaluates
both policy alternatives against the same trusted granted scopes.  This keeps
DPoP replay protection enabled and ensures a proof `jti` is consumed at most
once for the HTTP request.

### Request-lifetime security state

`ServerCallContext.state` carries two Nebula-owned values for the duration of
the A2A call:

```text
agent_nebula.security.request
    normalized request credential material required for deferred skill-only
    authentication

agent_nebula.security.principals
    trusted successful authentication results keyed logically by advertised
    scheme name
```

The normalized request security material exists because a skill requirement
may introduce a mechanism that was not required at AgentCard ingress.  It is
request-local only: it must not be logged, persisted, placed in task artifacts,
or exposed to `AgentExecutor`.  Once a scheme is authenticated, later policy
checks use the trusted principal cache instead of the raw credential.

### Scheme families

The evaluator is scheme-neutral.  Concrete authenticators enforce the A2A 1.0
security scheme families supported by the Platform configuration:

- API key: extract according to the advertised location/name and verify with the configured key verifier.
- HTTP authentication: verify the advertised HTTP authentication scheme with the configured verifier.
- OAuth 2.0: validate the access token and, when configured, DPoP proof/binding once; expose trusted granted scopes for policy evaluation.
- OpenID Connect: validate the bearer JWT against configured issuer/audience/discovery policy; expose trusted claims/scopes for policy evaluation.
- Mutual TLS: use the validated transport client certificate/identity and configured trust policy.

A server fails configuration validation when an AgentCard or AgentSkill
references a scheme that is undefined or has no configured authenticator.

### Security invariants

The implementation follows these invariants:

1. AgentCard and AgentSkill requirements are independent policy boundaries.
2. `securitySchemes` defines mechanisms; it does not itself require authentication.
3. Requirement entries are OR alternatives; schemes inside an entry are ANDed.
4. Authentication is performed lazily when a required scheme is first encountered.
5. A given advertised scheme is authenticated at most once per server call.
6. Authentication is scope-neutral; OAuth/OIDC scopes are authorization policy.
7. Successful principals are reused across agent and skill policy checks.
8. DPoP proof validation/replay processing is never repeated for another policy check.
9. Security completes before `DefaultRequestHandler` enters `AgentExecutor` business logic.
10. Raw request credential material retained for deferred authentication is request-local and must never be logged or persisted.


## Implementation files

- `agent_nebula_platform/a2a/security/server.py`: security scheme authenticators, requirement evaluation, authenticated request state, and `ServerCallContextBuilder` integration.
- `agent_nebula_platform/a2a/security/request_handler.py`: transport-neutral pre-execution AgentSkill authorization wrapper.
- `agent_nebula_platform/a2a/server.py`: mounts the wrapped `RequestHandler` into official JSON-RPC, HTTP+JSON, and gRPC SDK bindings.
- `agent_nebula_secureagent/a2a/server.py`: creates `DefaultRequestHandler`, wraps it with `A2AAuthorizedRequestHandler`, and keeps `_SkillDispatcher` limited to execution routing.

## Architectural rule

Security must be complete before `AgentExecutor` is entered. Agent Nebula uses official SDK extension/boundary interfaces wherever possible and does not duplicate A2A transport parsing merely to perform authorization.
