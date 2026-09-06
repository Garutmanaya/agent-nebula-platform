"""Embedded preset for existing FastAPI applications.

The embedded preset composes runtime plugins around caller-owned dependencies.
It never starts a server, configures global logging, or creates network clients.
"""

from __future__ import annotations

from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.presets.composition import compose_feature_plugins
from agent_nebula_platform.platform.presets.models import (
    EmbeddedPresetOptions,
    RuntimeFeatureComponents,
)
from agent_nebula_platform.platform.runtime import AgentRuntime


def build_embedded_runtime(
    *,
    context: RuntimeContext,
    components: RuntimeFeatureComponents,
    options: EmbeddedPresetOptions,
) -> AgentRuntime:
    """Build a runtime that attaches selected capabilities to an existing app."""

    return AgentRuntime(
        context=context,
        plugins=compose_feature_plugins(
            components=components,
            server=options,
        ),
    )
