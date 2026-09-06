# Agent Nebula Platform Documentation

This directory documents the current `agent-nebula-platform` architecture by capability. The source tree is authoritative when implementation and documentation differ.

| Area | Document | Purpose |
| --- | --- | --- |
| A2A | [a2a.md](a2a.md) | Official A2A 1.0 client/server integration, configuration and security |
| Security | [security.md](security.md) | OAuth operational services and SDK boundary |
| Skills | [skills.md](skills.md) | Transport-neutral skill registration and invocation |
| A2UI | [a2ui.md](a2ui.md) | Declarative UI, actions, sessions and validation |
| Integrations | [integrations.md](integrations.md) | Optional Agent Nebula Registry integration |
| MCP | [mcp.md](mcp.md) | Current MCP support status and protocol boundary |
| Platform | [platform.md](platform.md) | Plugin lifecycle, composition, configuration, transport and operational services |

The dependency direction is:

```text
agent-nebula-secureagent
        ↓
agent-nebula-platform
        ↓
agent-nebula-sdk
```
