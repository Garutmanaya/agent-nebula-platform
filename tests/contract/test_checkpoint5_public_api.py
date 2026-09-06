"""Checkpoint 5 public API and capability contracts."""

from agent_nebula_platform.platform.capabilities import (
    RuntimeCapability,
    require_available,
)
from agent_nebula_platform.platform.presets import (
    EmbeddedPresetOptions,
    RuntimeFeatureComponents,
    StandaloneAgent,
    StandaloneRuntimeSettings,
    build_embedded_runtime,
    build_standalone_agent,
)


def test_checkpoint5_preset_exports_are_available() -> None:
    """Preset APIs are importable and capability metadata is current."""

    assert EmbeddedPresetOptions
    assert RuntimeFeatureComponents
    assert StandaloneAgent
    assert StandaloneRuntimeSettings
    assert build_embedded_runtime
    assert build_standalone_agent
    assert require_available(RuntimeCapability.PRESETS).checkpoint == "5"
