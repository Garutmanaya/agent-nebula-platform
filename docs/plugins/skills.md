# Skills Plugin

Skills are typed business-operation declarations.

A `SkillDefinition` identifies:

- stable skill ID;
- sync or async handler;
- exact required scopes.

The registry rejects duplicate IDs. `SkillInvocationService` resolves the skill, authenticates protected requests, enforces all required scopes, and invokes the handler.

Runtime initialization can validate skill declarations against the authoritative Agent Card and Protected Resource Metadata:

```text
runtime skill exists in Agent Card
runtime scopes exactly match Agent Card required_scopes
required_scopes ⊆ scopes_supported
```

Business handlers remain responsible for domain input validation and authorization beyond protocol scope checks.
