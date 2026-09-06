# A2A OAuth and DPoP

A2A 1.0 declares OAuth through the standard `OAuth2SecurityScheme`; it does not make DPoP mandatory.
Agent Nebula therefore does not add a proprietary field to the A2A security scheme.

DPoP policy is published by OAuth Protected Resource Metadata (RFC 9728):

- `dpop_bound_access_tokens_required` determines whether this resource requires DPoP-bound tokens.
- `dpop_signing_alg_values_supported` advertises accepted DPoP proof algorithms.
- RFC 8414 authorization-server metadata advertises authorization-server DPoP support.

Runtime maps this policy to the generic SDK resource-server implementation. When DPoP is required, requests use `Authorization: DPoP` plus the `DPoP` proof header. Otherwise the OAuth A2A authenticator accepts standard `Authorization: Bearer` and performs RFC 9068/RFC 8707 validation without proof-of-possession.
