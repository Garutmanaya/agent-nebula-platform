"""Capability catalog tests."""

from agent_nebula_platform.platform.capabilities import (
    RuntimeCapability,
    capability_catalog,
    require_available,
)


def test_catalog_contains_complete_planned_surface() -> None:
    """Every agreed runtime capability remains visible in the roadmap."""

    values = {item.capability for item in capability_catalog()}
    assert RuntimeCapability.OAUTH_CLIENT in values
    assert RuntimeCapability.PROTECTED_RESOURCE in values
    assert RuntimeCapability.A2UI in values
    assert RuntimeCapability.A2A_SERVER in values
    assert RuntimeCapability.PRESETS in values


def test_operational_capabilities_are_available() -> None:
    """Checkpoint 9 operational capabilities are publicly available."""

    assert require_available(RuntimeCapability.METRICS).checkpoint == "9"
    assert require_available(RuntimeCapability.TELEMETRY).checkpoint == "9"
    assert require_available(RuntimeCapability.SCHEDULER).checkpoint == "9"
