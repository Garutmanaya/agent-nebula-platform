"""Tests for the Agent Nebula A2A health extension."""

from a2a.types import AgentCapabilities, AgentCard

from agent_nebula_platform.platform.health import HealthEndpointConfiguration
from agent_nebula_platform.protocols.a2a.extensions.health import (
    NEBULA_HEALTH_EXTENSION_URI,
    ensure_health_extension,
)


def test_health_extension_advertises_absolute_endpoints() -> None:
    """Health metadata remains optional and independent from A2A interfaces."""
    card = AgentCard(
        name="test", description="test", version="1",
        capabilities=AgentCapabilities(), default_input_modes=["application/json"],
        default_output_modes=["application/json"], skills=[],
    )
    configuration = HealthEndpointConfiguration(
        health_url="https://example.test/demand/health",
        liveness_url="https://example.test/demand/health/live",
        readiness_url="https://example.test/demand/health/ready",
    )

    ensure_health_extension(card, configuration)

    extension = next(
        item for item in card.capabilities.extensions
        if item.uri == NEBULA_HEALTH_EXTENSION_URI
    )
    assert extension.required is False
    assert dict(extension.params) == {
        "healthUrl": "https://example.test/demand/health",
        "livenessUrl": "https://example.test/demand/health/live",
        "readinessUrl": "https://example.test/demand/health/ready",
    }
