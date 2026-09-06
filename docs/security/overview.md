# Security Overview

Agent Runtime enforces application integration boundaries while delegating protocol and cryptographic correctness to `agent-nebula-sdk`.

Core rules:

- TLS verification remains enabled;
- private keys and secrets are file-backed or host-supplied;
- OAuth scopes are exact opaque identifiers;
- protected operations validate token, DPoP, audience, method, URI, token hash, key binding, replay, and scopes;
- REST, A2A, tasks, and A2UI actions share the same protected skill boundary;
- A2UI documents cannot inject executable browser content;
- metrics and telemetry exclude reusable credentials;
- browser or client visibility controls are never treated as authorization.

