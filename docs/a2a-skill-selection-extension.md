# Agent Nebula A2A Skill-Selection Extension

## Purpose

Agent Nebula SecureAgent supports deterministic business skills such as `inventory.get` or `travel.book_flight`. The official A2A protocol allows an Agent Card to advertise multiple `AgentSkill` entries, but the core `SendMessageRequest` does not contain a `skill_id` field. A2A intentionally sends a message to an agent rather than defining RPC-style skill dispatch.

Agent Nebula does **not** modify the official A2A protobuf/JSON models and does **not** restore the legacy Agent Nebula `method`/`params` wire format. Instead, it uses the official A2A extension mechanism to communicate a client-selected `AgentSkill.id`.

Extension URI:

```text
https://agentnebula.ai/extensions/a2a/skill-selection/v1
```

This extension provides deterministic dispatch without requiring an LLM at the provider.

## Standards boundary

The extension follows the A2A extension model:

1. The agent declares extension support in `AgentCard.capabilities.extensions`.
2. The client discovers the Agent Card and selects one advertised `AgentSkill.id`.
3. The client activates the extension using the A2A extension service parameter (`A2A-Extensions` for HTTP bindings; the official SDK maps service parameters for supported bindings).
4. The client places extension data in the existing `SendMessageRequest.metadata` map.
5. The server reads the activated extension from official `RequestContext.requested_extensions` and the data from official `RequestContext.metadata`.
6. The server validates the selected ID against its registered and advertised skills before dispatch.

No core A2A field, enum, method, transport, or state is changed.

## Agent Card declaration

Platform adds this declaration to the official Agent Card before it is published:

```json
{
  "uri": "https://agentnebula.ai/extensions/a2a/skill-selection/v1",
  "description": "Agent Nebula deterministic selection of an advertised AgentSkill.id using standard A2A extension metadata",
  "required": false
}
```

The extension is always advertised with `required: false`. Deterministic skill selection is an optional Agent Nebula capability, so generic A2A clients remain interoperable and may send ordinary A2A messages without activating the extension. Nebula-aware clients activate the extension when they need explicit `AgentSkill.id` selection.

If `a2aserver.conf` already declares this URI, it must also declare the extension as optional. Platform fails closed on a conflicting `required` value.

## Request metadata schema

The extension uses a URI-namespaced object inside `SendMessageRequest.metadata`:

```json
{
  "https://agentnebula.ai/extensions/a2a/skill-selection/v1": {
    "skillId": "travel.search_flights"
  }
}
```

Schema:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `skillId` | string | yes | Exact `AgentSkill.id` advertised by the target Agent Card |

`skillId` must be non-empty and must exactly match an advertised and executable skill. It is an identifier, not a natural-language intent.

## Client responsibilities

Skill selection is a **client-side responsibility**. The provider does not infer which skill the caller intended.

The Agent Nebula A2A client flow is:

```text
request / orchestration goal
        |
        v
resolve official Agent Card
        |
        v
select AgentSkill.id
        |
        +--> validate extension support
        |
        +--> read selected skill security requirements
        |
        +--> acquire least-privilege credentials/token
        |
        v
construct official SendMessageRequest
        |
        +--> metadata[extension URI].skillId
        +--> activate A2A extension
        |
        v
official a2a-python Client / transport
```

`A2AClientAdapter.send_message(..., skill_id=...)` performs protocol construction and validation after a higher-level caller has selected the skill. It does not perform LLM routing.

A client that does not use Agent Nebula or `a2a-python` can still use the extension by implementing the same published A2A extension contract with a standards-compliant A2A request.

## Server responsibilities

The provider receives an official A2A request through `DefaultRequestHandler` and `AgentExecutor`.

For a multi-skill provider:

```text
RequestContext
    |
    +--> requested_extensions contains extension URI
    |
    +--> metadata contains skillId
    |
    v
validate extension metadata
    |
    v
lookup registered skill by exact AgentSkill.id
    |
    v
execute @agent.skill handler
```

The server does not choose a skill from natural-language text. It only validates and dispatches the client's explicit selection.

For a single-skill provider, an extension-unaware generic A2A client may omit the extension. The only registered handler is then used. If the extension is activated, its metadata is still validated.

## Security and least privilege

Extension metadata is untrusted caller input. A selected skill must never be authorized merely because its ID appears in metadata.

When `skill_id` is selected, the Agent Nebula client security resolver prefers that `AgentSkill.security_requirements`. If the skill does not define its own requirements, card-level `AgentCard.security_requirements` apply. This allows OAuth credential acquisition to request the scopes associated with the selected capability before sending the A2A message.

The provider's normal protected-resource security remains authoritative. Extension processing does not bypass OAuth, DPoP, mTLS, API-key, OIDC, policy, or other configured controls.

Conceptually:

```text
selected skillId
      |
      v
published AgentSkill
      |
      v
skill security requirements/scopes
      |
      v
credential/token acquisition
      |
      v
A2A request + extension metadata
      |
      v
provider authentication/authorization
      |
      v
validated deterministic dispatch
```

## Failure behavior

Platform fails closed for these conditions:

- blank `skillId`;
- selected skill not advertised by the remote Agent Card;
- remote agent does not advertise the extension when the client requests deterministic skill selection;
- multi-skill provider receives a request without extension activation;
- extension is activated but its metadata is absent or malformed;
- selected skill is not registered by the provider;
- executable skill is not published in `a2aserver.conf`;
- duplicate executable skill IDs;
- conflicting `required` declaration for the extension.

## Compatibility

This extension is additive and does not fork A2A:

- official `AgentCard`, `AgentSkill`, `SendMessageRequest`, `Message`, `RequestContext`, `DefaultRequestHandler`, and transport clients remain in use;
- no field is added to an A2A core type;
- no custom A2A endpoint is introduced;
- no custom JSON-RPC method is introduced;
- no change to `a2a-python` is required;
- single-skill providers remain callable by generic A2A clients without the extension.

Multi-skill deterministic SecureAgent providers intentionally require extension-aware clients because core A2A does not define a first-class skill selector.

## Versioning

The version is part of the URI. Any breaking change to metadata shape or dispatch semantics requires a new URI, for example `/v2`. A client must not silently treat another extension version as compatible.
