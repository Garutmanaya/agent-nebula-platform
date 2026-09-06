"""Contract tests for the public Checkpoint 8 configuration API."""

from __future__ import annotations


def test_checkpoint8_configuration_api_is_importable() -> None:
    """Public configuration and plugin-setting types remain importable."""

    from agent_nebula_platform.platform.configuration import (
        FileSecretProvider,
        LayeredSettingsLoader,
        RuntimeHome,
        cli_overrides,
        environment_overrides,
    )
    from agent_nebula_platform.platform.presets import (
        RuntimePluginSettings,
        StandalonePluginSettings,
    )

    assert FileSecretProvider
    assert LayeredSettingsLoader
    assert RuntimeHome
    assert cli_overrides
    assert environment_overrides
    assert RuntimePluginSettings
    assert StandalonePluginSettings
