"""Agent Nebula A2A extension for operational health endpoint discovery."""

from __future__ import annotations

from a2a.types import AgentCard, AgentExtension

from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.platform.health import HealthEndpointConfiguration

NEBULA_HEALTH_EXTENSION_URI = "https://agentnebula.ai/extensions/a2a/health/v1"


def ensure_health_extension(
    agent_card: AgentCard, configuration: HealthEndpointConfiguration
) -> None:
    """Advertise independently configured health endpoints on an Agent Card.

    NEBULA A2A EXTENSION: health/v1 is informational and optional. Generic A2A
    clients do not need to understand it to invoke the agent. Platform owns the
    endpoint implementation; this module owns only its A2A representation.
    """
    expected_params = {
        "healthUrl": configuration.health_url,
        "livenessUrl": configuration.liveness_url,
        "readinessUrl": configuration.readiness_url,
    }
    for extension in agent_card.capabilities.extensions:
        if extension.uri != NEBULA_HEALTH_EXTENSION_URI:
            continue
        if extension.required:
            raise ConfigurationError(
                "Agent Nebula health extension must remain optional",
                details={"uri": NEBULA_HEALTH_EXTENSION_URI},
            )
        if dict(extension.params or {}) != expected_params:
            raise ConfigurationError(
                "Agent Nebula health extension conflicts with [health] configuration",
                details={"uri": NEBULA_HEALTH_EXTENSION_URI},
            )
        return

    agent_card.capabilities.extensions.append(
        AgentExtension(
            uri=NEBULA_HEALTH_EXTENSION_URI,
            description="Advertises operational health, liveness, and readiness endpoints.",
            required=False,
            params=expected_params,
        )
    )
