# Secure Skill Invocation Example

```python
async def reserve(invocation: SkillInvocation) -> SkillResult:
    reservation = await service.reserve(invocation.payload)
    return SkillResult(data=reservation)

skill = SkillDefinition(
    skill_id="parking.reserve",
    handler=reserve,
    required_scopes=("parking.reserve",),
)
```

For REST, A2A, tasks, or A2UI actions, the shared invocation service authenticates the request and verifies all exact required scopes before calling `reserve`.

The business service should still validate domain constraints such as ownership, availability, and idempotency.
