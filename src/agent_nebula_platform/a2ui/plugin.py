"""A2UI runtime capability plugin."""

from __future__ import annotations

from collections.abc import Sequence

from agent_nebula_platform.a2ui.models import (
    A2UI_STABLE_VERSION,
    A2UI_SUPPORTED_VERSIONS,
)
from agent_nebula_platform.a2ui.service import A2UIService
from agent_nebula_platform.a2ui.validation import (
    A2UIComponentPolicy,
    A2UIProtocolPolicy,
)
from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.plugins.base import RuntimePlugin


class A2UIPlugin(RuntimePlugin):
    """Register declarative surface validation and secure action dispatch."""

    def __init__(
        self,
        *,
        allowed_components: Sequence[str],
        allowed_functions: Sequence[str] = (),
        allowed_catalog_ids: Sequence[str] = (),
        supported_versions: Sequence[str] = A2UI_SUPPORTED_VERSIONS,
        preferred_version: str = A2UI_STABLE_VERSION,
        required: bool = True,
    ) -> None:
        self._component_policy = A2UIComponentPolicy(
            allowed_components=allowed_components,
            allowed_functions=allowed_functions,
        )
        self._protocol_policy = A2UIProtocolPolicy(
            supported_versions=supported_versions,
            preferred_version=preferred_version,
            allowed_catalog_ids=allowed_catalog_ids,
        )
        self._required = required

    @property
    def name(self) -> str:
        """Return the stable plugin identifier."""

        return "a2ui"

    @property
    def required(self) -> bool:
        """Return whether invalid A2UI composition is fatal."""

        return self._required

    async def initialize(self, context: RuntimeContext) -> None:
        """Register A2UI validation/capability services.

        Renderer events are transported by the A2UI A2A extension and are not
        mapped to AgentSkill identifiers by the runtime.
        """

        context.services.register(
            self.name,
            A2UIService(
                component_policy=self._component_policy,
                protocol_policy=self._protocol_policy,
            ),
        )

    async def close(self, context: RuntimeContext) -> None:
        """Remove the runtime-owned A2UI service."""

        context.services.remove(self.name)
