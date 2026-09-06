# A2A 1.0 Server Security

Agent Runtime interprets the official `AgentCard.security_schemes` and
`security_requirements` fields. Requirement entries are alternatives (OR); every
scheme inside one entry must authenticate successfully (AND). Scheme identifiers
are opaque Agent Card keys. Runtime dispatches only on the official
`SecurityScheme` protobuf oneof type.

`A2AServerSecurityService` validates at startup that every advertised scheme
family has a configured authenticator. A secured Agent Card therefore cannot be
published by Runtime while its protocol implementation is missing.

HTTP JSON-RPC and HTTP+JSON protocol routes are protected before the official
`a2a-python` dispatcher is entered. The public well-known Agent Card remains
readable so clients can discover the advertised authentication requirements.
Successful principals are retained in `request.scope["a2a.security"]`.

The existing Runtime protected-resource service can be adapted to an A2A OAuth2
scheme with `A2AOAuth2ProtectedResourceAuthenticator`. It preserves the existing
Agent Nebula SDK RFC 8707/RFC 9068/RFC 9449 validation path and therefore expects
a DPoP-bound access token and proof. It does not pretend that every OAuth2 or
OIDC deployment uses DPoP.

Other security families are supplied through the
`A2ASecuritySchemeAuthenticator` port. This keeps A2A interpretation in Runtime
and protocol validation outside it. Missing authenticators fail startup rather
than silently weakening the Agent Card.

Secured gRPC is currently rejected at startup. The official gRPC handler requires
a transport-specific authentication boundary to return correct gRPC
UNAUTHENTICATED/PERMISSION_DENIED status. Runtime deliberately does not expose an
insecure gRPC listener for a card that advertises security. A dedicated gRPC
security adapter is required before secured gRPC can be enabled.
