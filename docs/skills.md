# Skills

## Purpose

Skills are the Platform's protocol-neutral business capability model. A skill describes an invokable operation, its exact required scopes, its handler, and optional description. A skill is not an A2A `AgentSkill`; protocol-specific conversion belongs in the corresponding protocol adapter.

## Package layout

```text
skills/
├── models.py
├── plugin.py
├── registry.py
└── service.py
```

## Core model

`SkillDefinition` contains:

- `skill_id` — stable operation identifier;
- `required_scopes` — exact provider-specific scopes required to invoke it;
- `handler` — sync or async business handler;
- `description` — optional human-readable description.

Handlers receive a `SkillInvocation`, containing validated payload data and, when applicable, a trusted `AuthorizedRequestContext`. They return a `SkillResult` containing structured data, metadata, and an optional A2UI surface.

## Registration

`SkillRegistry` owns registered definitions and provides deterministic lookup. `SkillsPlugin` creates the registry and `SkillInvocationService`, then publishes them through the runtime service registry as:

```text
skills.registry
skills.invocation
```

If protected-resource metadata is supplied, initialization validates every skill's required scopes against `scopes_supported`. Missing scopes fail composition rather than weakening authorization.

## Invocation

The invocation service is the transport-neutral boundary. REST, A2A, A2UI actions, or future protocol adapters should resolve the requested operation and invoke the same skill service rather than create protocol-specific copies of business logic.

Conceptually:

```text
REST / A2A / A2UI action / future protocol
                 ↓
        SkillInvocationService
                 ↓
       authorization context
                 ↓
          business handler
                 ↓
            SkillResult
```

## A2UI results

A skill may return an `A2UISurface` in `SkillResult.ui`. This keeps the business result and optional declarative presentation result together without making the skill itself dependent on an HTTP or A2A transport.

## Extension rule

Keep skill definitions transport-neutral. Mapping a skill into an A2A Agent Card, MCP tool, REST route, or another protocol representation belongs in that protocol/transport integration.
