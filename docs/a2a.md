# A2A integration

The Platform integrates the **official A2A Python SDK** for A2A 1.0 protocol processing. It does not implement a competing A2A wire protocol. A2A agents can run without Agent Nebula Registry onboarding.

## Current source layout

```text
src/agent_nebula_platform/a2a/
├── client.py                 # Client-side integration
├── server.py                 # Server-side integration
├── runtime.py                # A2A runtime composition
├── config/
│   ├── client.py             # Client configuration
│   └── server.py             # Server configuration
├── security/
│   ├── client.py             # Client security integration
│   ├── server.py             # Server security integration
│   └── request_handler.py    # Request-handler security integration
└── extensions/
    ├── a2ui.py
    ├── health.py
    ├── schema_contract.py
    └── skill_selection.py
```

A2A protocol integration lives directly under `agent_nebula_platform/a2a/`. There is **no** `protocols/` package.

## Security ownership

The A2A integration interprets Agent Card security requirements and integrates authentication with the server and client. Operational OAuth clients, metadata, client registration and protected-resource authorization live in `security/oauth/`; reusable OAuth/JOSE/JWT/JWK/DPoP primitives live in `agent-nebula-sdk`. Scope requirements are enforced by the protected-resource and skill authorization layers, not by modifying A2A wire models.

See [security](security.md), [A2A security details](nebula-a2a-security.md), and [skill selection extension](a2a-skill-selection-extension.md).

## Configuration

A2A configuration examples are provided at `examples/a2aserver.conf.template` and `examples/a2aclient.conf.template`. Host runtime configuration and optional Registry onboarding remain separate from A2A protocol configuration.

## Extension boundaries

New A2A-specific integration belongs under `a2a/`. Generic OAuth/security services belong under `security/`, transport-neutral business skills under `skills/`, and generic lifecycle services under `platform/`. The official A2A SDK remains authoritative for protocol messages and request processing.
