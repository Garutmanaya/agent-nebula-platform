# OAuth and DPoP

## Caller flow

```text
OAuth client plugin
    → private_key_jwt and DPoP artifacts through SDK
    → token endpoint with RFC 8707 resource
    → RFC 9068 access token
    → DPoP-protected Provider request
```

## Provider flow

```text
Authorization: DPoP <token>
DPoP: <proof>
    ↓
SDK resource-server facade
    ↓
issuer, audience, exp/profile, htm, htu, ath, jkt, replay
    ↓
exact required scopes
    ↓
business skill
```

Token cache entries are isolated by exact resource, scope values, and DPoP key thumbprint. Tokens or proofs are not included in runtime events or A2A task snapshots.
