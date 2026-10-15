# Repository Engineering Guide

This repository contains `agent-nebula-platform`, the integration layer used by SecureAgent.

## Boundaries

- Use the official `a2a-sdk` for A2A protocol handling. Platform A2A integration lives in `src/agent_nebula_platform/a2a/`; do not recreate the removed `protocols/` package.
- Keep cryptographic primitives and protocol-security algorithms in `agent-nebula-sdk`. Platform composes security into server and client request paths.
- Keep application-specific business skills in consuming applications, not in Platform.
- Preserve public APIs and configuration compatibility unless a change is explicitly required.
- Do not introduce duplicate protocol adapters, authentication paths, or configuration APIs.

## Runtime and security

- Follow the current configuration and lifecycle implementations; see [runtime](docs/runtime.md), [security](docs/security.md), and [A2A security](docs/nebula-a2a-security.md).
- Runtime path validation is not a substitute for OS/container filesystem isolation. Do not claim that the library alone blocks access outside `/run/agent-nebula`.
- Never commit credentials, private keys, tokens, or deployment-specific secrets.

## Verification

- Run applicable unit tests and lint checks for changes. Validate documentation links when changing Markdown.
- Keep protocol, plugin, and lifecycle documentation aligned with the actual source tree.

See [documentation index](docs/README.md) for architecture and capability details.
