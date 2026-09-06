# Protected Resource Plugin

The protected-resource capability authenticates Provider Agent requests before business dispatch.

Validation is delegated to SDK-composed resource-server services and includes:

- issuer;
- exact audience;
- expiration and JWT profile checks;
- DPoP proof method and URI;
- access-token hash (`ath`);
- DPoP key binding;
- replay protection;
- exact method-specific scopes.

The runtime then applies provider-local authorization and invokes the registered skill. Authentication dependencies do not consume the business request body.

See [OAuth and DPoP](../security/oauth-dpop.md) and [Scopes](../security/scopes.md).
