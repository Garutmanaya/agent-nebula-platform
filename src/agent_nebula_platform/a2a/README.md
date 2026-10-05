# Agent Nebula Platform — A2A Frozen Requirements

This directory is the clean Agent Nebula integration boundary on top of the official `a2a-sdk`. **All code changes under this directory MUST follow this document.**

## Frozen ownership

1. `a2a-sdk` is authoritative for standard A2A protocol functionality.
2. This package contains only Agent Nebula functionality required on top of `a2a-sdk`: configuration integration, security integration, and Nebula-specific extension semantics.
3. Do not duplicate or wrap standard `a2a-sdk` models or operations, including AgentCard, AgentSkill, Message, Task, Artifact, AgentExecutor, RequestContext, EventQueue, Client operations, streaming, cancellation, push notifications, or protocol bindings.
4. Public boundaries use and return native `a2a-sdk` types. Do not convert native models to dictionaries merely to hide the SDK.
5. Agent Card is authoritative for interfaces, skills, capabilities, extensions, and security declarations.
6. A2A extensions use the standard A2A extension mechanism. Nebula code implements only Nebula-specific extension semantics.
7. A2UI protocol functionality does not belong in Platform. No A2UI surface, component, action, session, result-mapping, or rendering implementation may be added here.
8. No LLM-dependent protocol behavior is allowed.
9. Configuration, secrets, credentials, and mutable runtime state remain external to source code.
10. Legacy compatibility code stays outside this directory and must not be imported by this directory.

## Frozen structure

```text
a2a/
├── README.md
├── __init__.py
├── client.py
├── server.py
├── config/
│   ├── __init__.py
│   ├── client.py
│   └── server.py
├── security/
│   ├── __init__.py
│   ├── client.py
│   └── server.py
└── extensions/
    ├── __init__.py
    ├── health.py
    ├── schema_contract.py
    └── skill_selection.py
```

Do not add `models`, `services`, `adapters`, `interfaces`, `factories`, `plugins`, `execution`, or similar layering without first changing this frozen contract.

## Coding standards

- Keep modules small in responsibility and code paths direct.
- Prefer composition of official SDK objects over Agent Nebula wrappers.
- Use explicit type hints and native SDK types at public boundaries.
- Do not use wildcard imports. Keep package exports minimal and explicit.
- Do not duplicate constants or protocol definitions.
- Do not add speculative abstractions for hypothetical future implementations.
- Do not add compatibility aliases or dead migration code to this tree.
- Comments explain Agent Nebula-specific behavior or standards boundaries, not Python syntax.
- Configuration errors must fail explicitly; do not silently invent defaults for protocol/security facts advertised by an Agent Card.
- Security must integrate through official A2A SDK extension points such as client interceptors and server call-context builders.
- New functionality requires tests at the public boundary.
- A patch is not complete until formatting/static checks, imports, and targeted tests pass. Runtime success must not be claimed unless runtime execution occurred.

## Change test

Before adding code here, ask: **Would this functionality exist without Agent Nebula configuration, security, or a Nebula-specific extension?** If yes, it belongs to `a2a-sdk` or another standard library, not here.
