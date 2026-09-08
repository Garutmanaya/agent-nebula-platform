"""Client-side A2UI v1.0 binding on official A2A 1.x.

A2UI negotiation belongs here rather than in the generic A2A client adapter.
The module advertises renderer capabilities in Message.metadata and requests the
standard A2UI extension through the official A2A service-parameter mechanism.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from a2a.types import AgentCard

from agent_nebula_platform.a2ui.configuration import A2UIConfiguration
from agent_nebula_platform.a2ui.models import A2UI_STABLE_VERSION
from agent_nebula_platform.protocols.a2a.client.extension_context import (
    A2AClientExtensionContribution,
)

from .extension import A2UI_EXTENSION_URI

A2UI_RENDERER_CAPABILITIES_METADATA_KEY = "a2uiRendererCapabilities"


class A2UIClientExtension:
    """Contribute A2UI v1.0 negotiation to an A2A client call when enabled."""

    def __init__(self, configuration: A2UIConfiguration) -> None:
        self._configuration = configuration

    def prepare(
        self, agent_card: AgentCard, *, skill_id: str | None
    ) -> A2AClientExtensionContribution:
        del skill_id
        if not self._configuration.enabled:
            return A2AClientExtensionContribution()
        if not _supports_a2ui(agent_card):
            return A2AClientExtensionContribution()
        return A2AClientExtensionContribution(
            extension_uris=(A2UI_EXTENSION_URI,),
            message_metadata={
                A2UI_RENDERER_CAPABILITIES_METADATA_KEY: {
                    A2UI_STABLE_VERSION: {
                        "supportedCatalogIds": list(
                            self._configuration.supported_catalog_ids
                        )
                    }
                }
            },
        )


def _supports_a2ui(agent_card: AgentCard) -> bool:
    """Return whether the remote card advertises the optional A2UI binding."""

    return any(
        extension.uri == A2UI_EXTENSION_URI
        for extension in agent_card.capabilities.extensions
    )
