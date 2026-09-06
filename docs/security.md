# Security

## Responsibility

The Platform security layer turns reusable standards primitives from `agent-nebula-sdk` into operational runtime services. It must not create a second implementation of OAuth, JOSE, JWT, JWK, DPoP, or related RFC behavior.

```text
protocol adapter
      ↓
Platform security service
      ↓
agent-nebula-sdk
```

## OAuth layout

```text
security/oauth/
├── client/
├── metadata/
├── protected_resource/
└── registration/
```

### OAuth client

The client package contains identity, token/cache models, transport ports, HTTPX integration, protected HTTP support, service composition, and `OAuthClientPlugin`. It is reusable by protocol clients such as A2A.

### Metadata

The metadata package resolves authorization-server metadata and builds/publishes protected-resource metadata. Metadata handling is kept outside A2A because OAuth metadata is reusable across transports and protocols.

### Protected resource

The protected-resource package owns authenticated request context, protected-resource requests, authorization policy ports, exact-scope authorization, service composition, FastAPI route protection, and `ProtectedResourcePlugin`.

Skills and A2A may consume this service, but token validation and authorization remain owned here.

### Registration

The registration package contains the Platform plugin and transport integration for OAuth client registration. Standards-level registration behavior remains delegated to the SDK.

## Scope handling

Skill scopes are treated as exact values. The skills plugin can validate required skill scopes against protected-resource metadata during initialization. Platform code must not silently normalize or reinterpret scope names.

## TLS and mTLS

TLS listener/transport concerns and OAuth authentication mechanisms are separate. Possessing a CA/trust bundle does not imply mTLS. Protocol configuration must explicitly select the authentication mechanism being used.

## Dependency boundary

Security code may depend on `agent-nebula-sdk`. SDK code must never import Platform. Developer-facing SecureAgent code should request Platform security capabilities rather than implement security protocols itself.
