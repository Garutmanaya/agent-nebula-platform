"""Skill registry capability plugin."""

from __future__ import annotations

from collections.abc import Iterable

from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.platform.plugins.base import RuntimePlugin
from agent_nebula_platform.security.oauth.metadata import (
    ProtectedResourceMetadataProvider,
)
from agent_nebula_platform.skills import (
    SkillDefinition,
    SkillInvocationService,
    SkillRegistry,
)


class SkillsPlugin(RuntimePlugin):
    """Register skills and validate their scopes against resource metadata."""

    def __init__(
        self,
        *,
        definitions: Iterable[SkillDefinition],
        metadata_provider: ProtectedResourceMetadataProvider | None = None,
        required: bool = True,
    ) -> None:
        self._registry = SkillRegistry(tuple(definitions))
        self._metadata_provider = metadata_provider
        self._required = required

    @property
    def name(self) -> str:
        """Return the stable plugin identifier."""

        return "skills"

    @property
    def required(self) -> bool:
        """Return whether invalid skill composition is fatal."""

        return self._required

    async def initialize(self, context: RuntimeContext) -> None:
        """Validate exact scopes and register the skill registry and service."""

        protected_document = None
        if self._metadata_provider is not None:
            protected_document = (
                self._metadata_provider.get_protected_resource_metadata()
            )
            supported = tuple(
                str(item)
                for item in protected_document.document.get("scopes_supported", ())
            )
            for definition in self._registry.definitions():
                missing = sorted(set(definition.required_scopes) - set(supported))
                if missing:
                    raise ConfigurationError(
                        "Skill requires scopes absent from protected-resource metadata",
                        details={
                            "skill_id": definition.skill_id,
                            "missing_scopes": missing,
                        },
                    )

        protected_resource = None
        if "oauth.protected_resource" in context.services.names():
            from agent_nebula_platform.security.oauth.protected_resource import (
                ProtectedResourceService,
            )

            protected_resource = context.services.require(
                "oauth.protected_resource", ProtectedResourceService
            )
        service = SkillInvocationService(
            registry=self._registry,
            protected_resource=protected_resource,
        )
        context.services.register("skills.registry", self._registry)
        context.services.register("skills.invocation", service)

    async def close(self, context: RuntimeContext) -> None:
        """Remove runtime-owned skill services."""

        context.services.remove("skills.invocation")
        context.services.remove("skills.registry")
