# A2A Server Configuration

Agent Runtime treats `a2aserver.conf` as the external, deployment-owned source
for the A2A 1.0 Agent Card. The file is TOML and mirrors the official
`a2a-python` protobuf field names using Python-style snake case. Runtime does
not maintain a second Agent Card domain model.

The container entrypoint may render `a2aserver.conf.template` with deployment
environment values before process startup. Runtime reads only the rendered
file. Secret values such as API keys, OAuth private keys, client secrets, and
TLS private keys must remain in the external secret/certificate filesystem and
must not be published in the Agent Card.

## Runtime flow

```text
a2aserver.conf.template
        -> container environment rendering
        -> a2aserver.conf
        -> A2AServerConfigurationLoader
        -> A2AAgentCardFactory
        -> official a2a.types.AgentCard
        -> A2AAgentCardValidator
```

`A2AAgentCardValidator` delegates A2A protobuf REQUIRED-field checks to the
official SDK. Runtime adds only publication invariants that require
cross-field knowledge: absolute interface URLs, unique skill IDs, a concrete
security-scheme type, non-empty security requirements, and references to
security schemes defined by the same Agent Card.

Security requirement tables use the A2A OR-of-AND model directly. Each
`[[agent_card.security_requirements]]` table is an OR alternative; every entry
inside its `schemes` map must be satisfied together.

See `examples/a2aserver.conf.template` for a complete template covering the
A2A 1.0 Agent Card surface. Optional sections can be removed by individual
agents.

## Step 2: server interface activation

Runtime derives the active A2A transports directly from `agent_card.supported_interfaces`.
`JSONRPC` and `HTTP+JSON` interfaces are mounted on the caller-owned FastAPI application using the official `a2a-python` route factories. `GRPC` interfaces are served with the official `GrpcHandler`; install the `a2a-grpc` Runtime extra when a card advertises GRPC. An advertised interface that Runtime cannot implement causes startup to fail rather than publishing a false capability.

The Runtime does not infer transports from `application.conf` and does not enable transports that are absent from the Agent Card. Step 2 requires an official `a2a.server.request_handlers.RequestHandler` supplied by the host. Request execution/security policy remains separate from transport wiring; A2A security enforcement is Step 3.
