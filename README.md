# Agent Nebula Platform

`agent-nebula-platform` is the reusable middleware between developer-facing [SecureAgent](https://github.com/garutmanaya/agent-nebula-secureagent), the official A2A Python SDK, and [Agent Nebula SDK](https://github.com/garutmanaya/agent-nebula-sdk) security primitives. It provides protocol integration, configuration, security composition and runtime services so agent authors can focus on skills rather than repeatedly implementing server lifecycle, authentication and observability.

## Why use the Platform?

Applications can select capabilities through plugins rather than adopting a monolithic agent server. The Platform composes A2A client/server operations, security requirements advertised by Agent Cards, OAuth clients and protected resources, skill invocation, A2UI, optional Registry onboarding, and operational services. Protocol handling remains with the official `a2a-sdk`; cryptographic and OAuth standards primitives remain in `agent-nebula-sdk`.

```text
SecureAgent / host application
             |
agent-nebula-platform
  |-- a2a/              A2A SDK integration and Agent Card security
  |-- security/oauth/   OAuth client, registration and protected resources
  |-- skills/           Transport-neutral skill dispatch
  |-- a2ui/             Declarative UI and action integration
  |-- integrations/     Optional Agent Nebula onboarding
  `-- platform/         Lifecycle, plugins, configuration, telemetry, metrics
             |
   official a2a-sdk + agent-nebula-sdk
```

See [Platform architecture](https://github.com/garutmanaya/agent-nebula-platform/blob/main/docs/platform.md) and [documentation index](https://github.com/garutmanaya/agent-nebula-platform/blob/main/docs/README.md).

## Protocols

**A2A 1.0** is implemented using the official Python SDK, including client/server integration and security-scheme handling. **A2UI 1.0** provides declarative UI data and actions over A2A; it is not a separate agent transport. **MCP** is planned, not yet implemented. See [A2A](https://github.com/garutmanaya/agent-nebula-platform/blob/main/docs/a2a.md), [A2UI](https://github.com/garutmanaya/agent-nebula-platform/blob/main/docs/a2ui.md), and [MCP status](https://github.com/garutmanaya/agent-nebula-platform/blob/main/docs/mcp.md).

## Security and authorization

The Platform interprets A2A Agent Card security declarations and composes supported authentication adapters with OAuth client and protected-resource services. It supports security integration for API keys, HTTP authentication, OAuth/OIDC and TLS/mTLS as configured by the host and advertised by the agent. Reusable OAuth, JOSE/JWT, JWK and DPoP primitives are delegated to `agent-nebula-sdk`; protected-resource authorization enforces exact required skill scopes. Optional [Agent Nebula](https://agentnebula.ai) integration enables hosted registration, discovery, OAuth and policy-managed access; those hosted services are distinct from the local Platform package. See [security](https://github.com/garutmanaya/agent-nebula-platform/blob/main/docs/security.md), [A2A security integration](https://github.com/garutmanaya/agent-nebula-platform/blob/main/docs/nebula-a2a-security.md) and [Registry integration](https://github.com/garutmanaya/agent-nebula-platform/blob/main/docs/integrations.md).

## Plugins and lifecycle

Capabilities are assembled through `RuntimePlugin` and `PluginRegistry`, with pre-server and post-server initialization, required/optional failure handling, health/readiness, and reverse-order shutdown. Available plugin areas include skills, A2UI, OAuth clients, protected resources, client registration, Registry onboarding, metrics, telemetry and scheduling. See [plugins and lifecycle](https://github.com/garutmanaya/agent-nebula-platform/blob/main/docs/platform.md) for contracts and operational behavior.

## Runtime configuration and filesystem permissions

The runtime path resolver provides **configured-root containment**, not an operating-system sandbox. `runtime_path()` confines paths to its configured runtime root; `shared_path()` may also permit the configured product root. The resolver does **not** enforce a global `/run/agent-nebula`-only rule, and Python code cannot prevent arbitrary filesystem access by other process components. For a deployment requiring writable runtime state **only** under `/run/agent-nebula`, configure that directory as the writable runtime mount and enforce restrictions with OS/container permissions and read-only mounts. Other paths may still be required read-only for Python packages, certificates and configuration. See [runtime and isolation](https://github.com/garutmanaya/agent-nebula-platform/blob/main/docs/runtime.md).

## Observability and operations

The Platform provides plugin health/readiness, lifecycle events, metrics, telemetry, retry, scheduling and execution tracing. Enable and configure these capabilities in the host composition rather than assuming all are active by default. See [runtime services](https://github.com/garutmanaya/agent-nebula-platform/blob/main/docs/platform.md) and [observability](https://github.com/garutmanaya/agent-nebula-platform/blob/main/docs/observability.md).

## Install

Python 3.12 is required. The Platform supports Agent Nebula SDK 5.x. Install the latest published release:

```bash
pip install agent-nebula-platform
```

For examples and application-level usage, see the [SecureAgent examples repository](https://github.com/garutmanaya/agent-nebula-secureagent-examples) and the [documentation index](https://github.com/garutmanaya/agent-nebula-platform/blob/main/docs/README.md).

## License

Apache License 2.0. See [LICENSE](https://github.com/garutmanaya/agent-nebula-platform/blob/main/LICENSE).
