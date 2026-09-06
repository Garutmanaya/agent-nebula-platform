# OAuth Client Plugin

The OAuth client capability orchestrates SDK-composed client-credentials behavior.

## Supported security behavior

- RFC 7523 `private_key_jwt` through `agent-nebula-sdk`;
- RFC 8707 resource indicators;
- RFC 9449 DPoP token-request proofs;
- DPoP-protected outbound request headers;
- exact opaque scope values;
- token caching isolated by resource, ordered scope set, and DPoP key thumbprint.

## Boundary

Agent Runtime owns request orchestration, cache policy, and plugin exposure. The SDK owns assertion creation, JWK/thumbprint logic, DPoP, JWT, and protocol validation.

Provider-specific scopes must come from the selected resource and applicable policy, never a global runtime allowlist.
