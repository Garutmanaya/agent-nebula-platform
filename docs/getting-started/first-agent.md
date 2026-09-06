# Build a First Agent

A runtime-managed agent typically provides:

1. complete Agent Card;
2. complete Protected Resource Metadata when acting as a resource server;
3. one or more typed skills;
4. SDK-composed OAuth client and/or protected-resource services;
5. selected runtime plugins or a preset.

## Define a skill

```python
from agent_runtime.skills import SkillDefinition, SkillInvocation, SkillResult

async def search(invocation: SkillInvocation) -> SkillResult:
    return SkillResult(data={"items": []})

skill = SkillDefinition(
    skill_id="catalog.search",
    handler=search,
    required_scopes=("catalog.search",),
)
```

## Supply authoritative documents

Use complete existing documents or the typed builders. Runtime initialization validates runtime skill scopes against the Agent Card and `scopes_supported`.

## Compose security

Construct OAuth and protected-resource services through `agent-nebula-sdk`; inject them into runtime components. Agent Runtime does not create private keys or implement token validation independently.

## Select a preset

Use standalone mode for a new Agent Studio agent and embedded mode for an existing application. See [Embedded versus standalone](../architecture/embedded-vs-standalone.md).
