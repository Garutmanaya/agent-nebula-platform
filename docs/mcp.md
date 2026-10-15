# MCP

## Current status

MCP is not implemented in the current `agent-nebula-platform` source tree. There is no `mcp/` package, MCP plugin, MCP client/server adapter, or MCP configuration loader in this repository today.

The Platform architecture reserves MCP as a protocol integration category rather than treating it as a skill, security, or Agent Nebula Registry feature.

## Intended boundary

When MCP support is added, MCP-specific code should be grouped under:

```text
mcp/
├── client/
├── server/
└── security/    # only MCP-specific security interpretation/adapters
```

The exact package structure should follow the capabilities actually adopted from the official MCP ecosystem rather than being created speculatively.

## Reuse requirements

MCP integration should reuse existing Platform capabilities where applicable:

```text
MCP protocol adapter
       ↓
transport-neutral Platform services
       ├── skills
       ├── OAuth/security
       ├── lifecycle/plugins
       ├── configuration
       ├── health/telemetry/metrics
       └── Agent Nebula integration (optional)
```

MCP must not create a second business-skill registry or duplicate OAuth implementation merely because those capabilities are exposed through MCP.

## Plugin model

Any future MCP server/client runtime capability should participate through the same `RuntimePlugin` lifecycle used by A2A and other Platform capabilities. If MCP is implemented, its concrete plugins would belong to the MCP integration; only generic plugin contracts belong under `platform/plugins/`.

## Registry independence

As with A2A, protocol support should not require Agent Nebula Registry integration unless the application explicitly enables that integration.
