# A2A Integration

## Purpose

Agent Nebula Platform integrates the official A2A 1.0 Python SDK rather than implementing a private A2A protocol. The Platform layer supplies operational configuration, client/server composition, security interpretation, execution bridging, and lifecycle integration around the official SDK.

A2A is independent of Agent Nebula Registry integration. An A2A agent can operate without onboarding or registering with Agent Nebula.

## Package layout

```text
protocols/a2a/
├── client/
│   ├── client_adapter.py
│   ├── client_configuration.py
│   ├── client_credentials.py
│   ├── client_security.py
│   ├── client_service.py
│   └── discovered_oauth.py
├── security/
│   ├── oauth_security.py
│   ├── protected_resource.py
│   ├── security.py
│   └── standard_security.py
└── server/
    ├── composition.py
    ├── execution.py
    ├── plugin.py
    ├── server_adapter.py
    └── server_interfaces.py
```

## Server

The server package connects official A2A request handling to Platform lifecycle and security services.

`A2AServerPlugin` is the plugin boundary used by Platform composition. The server adapter owns A2A HTTP-facing integration, while the official A2A `RequestHandler` remains the protocol request-processing implementation. Server execution code bridges transport-neutral business handlers into the A2A execution model.

A2A server composition requires an official A2A `AgentCard` and `RequestHandler`. The preset composer only enables the A2A plugin when those components are present and A2A is enabled for the host.

## Client

The client package provides:

- typed A2A client configuration;
- TLS configuration;
- credential providers for API key, HTTP authentication, mTLS, OAuth2 and OIDC;
- security requirement resolution;
- client interception for applying selected credentials;
- A2A client service creation and invocation;
- discovered OAuth support.

The client reads the remote Agent Card and uses the advertised security information to select the appropriate configured credential mechanism. OAuth-specific operational work is delegated to Platform OAuth services, which in turn use `agent-nebula-sdk` for standards-level behavior.

## Security layering

A2A security has three distinct responsibilities:

```text
protocols/a2a/security
    interprets A2A Agent Card security schemes and requirements
            ↓
security/oauth
    provides operational OAuth client/protected-resource services
            ↓
agent-nebula-sdk
    implements reusable OAuth/JOSE/JWT/JWK/DPoP and RFC primitives
```

`A2AServerSecurityService` evaluates the Agent Card security requirements and delegates each scheme to an `A2ASecuritySchemeAuthenticator`. OAuth2 can be backed by `A2AOAuth2ProtectedResourceAuthenticator` and the Platform protected-resource service.

The A2A package also contains standard security adapters for non-OAuth schemes supported by the client/server security contracts.

## OAuth discovery and client registration

When OAuth is advertised by an A2A provider, the A2A client can use discovered OAuth metadata and Platform OAuth services. Dynamic client registration is an OAuth concern, not an A2A protocol reimplementation. Client identity returned by the authorization server is persisted/reused by the corresponding OAuth integration rather than invented by A2A.

## Protected resources

`protocols/a2a/security/protected_resource.py` converts A2A-facing security information into the Platform protected-resource composition required by an A2A server. Token validation and authorization remain in `security/oauth/protected_resource/`; A2A code only interprets and connects the protocol-level declaration.

## Configuration

A2A-specific configuration belongs to A2A configuration, not generic application configuration. The repository includes example templates:

```text
examples/a2aserver.conf.template
examples/a2aclient.conf.template
```

Generic deployment/runtime settings remain separate from A2A protocol settings. Agent Nebula Registry settings are also separate because Registry participation is optional.

## Extension rule

New A2A-specific behavior belongs under `protocols/a2a/`. Reusable OAuth or security behavior must not be implemented there merely because A2A consumes it; it belongs under `security/` or `agent-nebula-sdk` according to responsibility.

## Agent Nebula deterministic skill selection

Multi-skill deterministic providers use the formal Agent Nebula A2A skill-selection extension rather than modifying core A2A request models. Skill selection occurs on the client; the provider validates and dispatches the selected advertised `AgentSkill.id`. See [Agent Nebula A2A Skill-Selection Extension](a2a-skill-selection-extension.md) for the complete wire contract, security behavior, failure semantics, and compatibility rules.

## Development protocol trace

Platform provides an opt-in logical protocol trace for diagnosing A2A 1.0 and
A2UI-over-A2A exchanges. The trace is emitted immediately around the official
A2A SDK boundary; it is not a second transport implementation and does not alter
messages.

Set `ANU_A2A_PROTOCOL_TRACE=true` on the client and/or provider process to emit
redacted structural events through the
`agent_nebula_platform.protocols.a2a.trace` logger. Add
`ANU_A2A_PROTOCOL_TRACE_PAYLOADS=true` only in a controlled development
environment when the normalized A2A request/response documents are also needed.
Authorization headers, API keys, OAuth tokens, DPoP material, cookies, passwords,
private-key fields, and other secret-bearing values are recursively redacted.

Typical events are `agent_card.resolved`, `request.send`, `request.receive`,
`response.map`, and `response.receive`. A2UI-aware summaries show advertised
extension parameters, renderer capability metadata, the A2UI MIME type, message
type, surface/catalog identifiers, and component counts. This makes catalog
negotiation and A2UI DataPart flow observable without decrypting HTTPS traffic.

Protocol tracing is disabled by default and the no-op tracer does not materialize
payload documents. Tests or host applications may inject another implementation
of `A2AProtocolTracer` without changing client, server, security, or A2UI logic.
