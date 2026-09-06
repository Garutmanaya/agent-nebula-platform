# Security Policy

Agent Runtime delegates standards and cryptography to `agent-nebula-sdk` and keeps application integration separate.

## Protected skill and A2UI action requests

A protected skill or A2UI action cannot execute unless:

- an access token is present using the DPoP authorization scheme;
- a DPoP proof is present;
- the access token satisfies RFC 9068 validation;
- issuer and audience are exact;
- DPoP method, URI, token hash, key binding, and replay checks succeed;
- every exact method-specific scope is granted.

## A2UI trust boundary

The agent may send declarative A2UI messages only. The runtime:

- requires an explicit approved component catalog;
- rejects unapproved component types;
- rejects raw HTML and executable-script fields;
- denies renderer-local function calls unless explicitly allowlisted;
- validates that all messages target the declared surface;
- validates create/update/delete ordering;
- routes renderer events only through configured action-to-skill bindings;
- does not allow an action payload to select an arbitrary URL or bypass skill authorization.

The renderer remains responsible for native component implementation, local state, visual styling, and client-side sandboxing. Client validation is not a substitute for server-side business validation.

## Host responsibilities

The host must:

- serve through HTTPS with peer-verifiable certificates;
- supply explicit trust bundles;
- protect private-key and API-key files;
- configure the SDK resource-server facade and replay store correctly;
- avoid logging full security headers;
- provide a trusted renderer component catalog;
- validate business input again inside skill handlers;
- use a production-grade server and lifecycle configuration.

## Standalone preset security

The standalone preset requires explicit TLS trust and HTTPS listener material.
It creates an HTTPX client with hostname and peer verification enabled and does
not expose a `verify=False` option. Managed file paths are resolved beneath the
configured runtime root and path traversal is rejected. Console event logging
uses a named logger and does not configure the process root logger. Tokens,
private keys, API keys, assertions, and DPoP proofs are not included in preset
events.

## A2A task security

Protected A2A tasks validate the access token, DPoP proof, target URI, HTTP
method, replay state, and exact skill scopes before task creation. Task control
operations reauthenticate the caller and compare the trusted subject and
client identifier with the stored task owner. Raw tokens, proofs, and callback
URLs are never persisted in task snapshots or emitted through runtime events.


## Discovery and resource metadata

Protected Resource Metadata generated through the runtime is validated by the Agent Nebula SDK. Agent Card skill scopes, runtime skill scopes, and `scopes_supported` are compared as exact opaque strings. The runtime does not translate punctuation, case, or namespace conventions. Unknown Agent Card and RFC extension members are preserved rather than reconstructed.

## Configuration and secret controls

Managed mode requires an explicit `AGENT_RUNTIME_HOME` or caller-provided root.
Relative certificate, key, trust, state, and secret paths are resolved beneath
that root, and traversal outside the root is rejected. File-backed secret
values are read only through the secret-provider boundary and are never added
to configuration error details or event records.

## Operational data security

Metrics and telemetry must contain identifiers and outcomes, not reusable
credentials. Runtime-provided events never include access tokens, API keys,
private keys, assertions, DPoP proofs, or complete authorization headers.
Telemetry destinations are caller-approved sinks; the runtime does not accept
arbitrary network callback URLs.

The JSON-lines sink writes only to the explicit normalized path supplied by the
host. Deployments should apply operating-system permissions appropriate for the
sensitivity of correlation IDs and operational metadata.
