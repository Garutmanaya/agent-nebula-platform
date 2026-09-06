# A2A 1.0 client configuration

Agent Runtime uses the official `a2a-python` client implementation. It does not
reimplement A2A client transports, Agent Card resolution, or transport selection.

`a2aclient.conf` contains local client capabilities. The target Agent Card remains
remote and authoritative. Runtime resolves it through the official
`A2ACardResolver`, then supplies it to the official `ClientFactory`.

## Ownership

- `a2aclient.conf`: local transport behavior, output modes, timeout, TLS trust and
  optional client TLS identity.
- remote Agent Card: interfaces, capabilities, security schemes and security
  requirements.
- Runtime: verified transport construction and lifecycle.
- `a2a-python`: Agent Card resolution, interface selection and protocol clients.
- Step 5 security negotiation: selects credentials/interceptors from the remote
  Agent Card. Step 4 intentionally does not choose OAuth, API key, OIDC or mTLS.

## Transport selection

`supported_protocol_bindings` is an ordered list of local capabilities. With
`use_client_preference = false` (recommended), the official SDK preserves the
server's `supportedInterfaces` preference while restricting selection to transports
supported locally. Setting it to `true` makes the configured client order win.

Supported values are `JSONRPC`, `HTTP+JSON`, and `GRPC`. gRPC requires the
Runtime `a2a-grpc` optional dependency.

## TLS

`trust_bundle` is mandatory. Runtime never disables certificate or hostname
verification. `certificate_file` and `private_key_file` are optional but must be
configured together. Supplying a client certificate makes the transport capable
of mTLS; it does not mean every target requires mTLS.

## Security boundary

No security mechanism is selected by scheme name or local preference in Step 4.
The client first obtains the remote standard Agent Card. Step 5 will evaluate its
OR-of-AND `securityRequirements`, discover OAuth/OIDC metadata where applicable,
and construct official client interceptors from locally available credentials.
