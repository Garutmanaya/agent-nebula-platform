"""Thread-safe-at-composition skill registry and dispatch service."""

from __future__ import annotations

import inspect

from agent_nebula_platform.platform.errors import ConfigurationError

from .models import SkillDefinition, SkillInvocation, SkillResult


class SkillRegistry:
    """Register exact skill identifiers and dispatch validated invocations."""

    def __init__(self, definitions: tuple[SkillDefinition, ...] = ()) -> None:
        self._definitions: dict[str, SkillDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: SkillDefinition) -> None:
        """Register one skill and reject ambiguous duplicate identifiers."""

        if definition.skill_id in self._definitions:
            raise ConfigurationError(
                f"Skill is already registered: {definition.skill_id}"
            )
        self._definitions[definition.skill_id] = definition

    def require(self, skill_id: str) -> SkillDefinition:
        """Return one declared skill or fail closed for unknown methods."""

        definition = self._definitions.get(skill_id)
        if definition is None:
            raise ConfigurationError(f"Skill is not registered: {skill_id}")
        return definition

    def definitions(self) -> tuple[SkillDefinition, ...]:
        """Return immutable skill definitions for diagnostics and metadata checks."""

        return tuple(self._definitions.values())

    async def invoke(self, invocation: SkillInvocation) -> SkillResult:
        """Invoke one sync or async business handler without transport coupling."""

        definition = self.require(invocation.skill_id)
        result = definition.handler(invocation)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, SkillResult):
            raise ConfigurationError(
                f"Skill handler must return SkillResult: {definition.skill_id}"
            )
        return result
