"""Unit tests for Checkpoint 8 layered configuration and secret handling."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI

from agent_nebula_platform.platform.configuration import (
    FileSecretProvider,
    RuntimeHome,
    environment_overrides,
)
from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.platform.events import NullEventSink
from agent_nebula_platform.platform.presets import (
    EmbeddedPresetOptions,
    RuntimeFeatureComponents,
    RuntimePluginSettings,
    StandaloneRuntimeSettings,
    build_embedded_runtime,
)
from agent_nebula_platform.platform.state import MemoryStateStore


class StubNebulaConnector:
    """Provide the connector contract without performing remote operations."""

    async def resolve_onboarding(self, payload):
        """Return no existing registration."""

        del payload

    async def onboard(self, payload):
        """Return a deterministic registration response."""

        del payload
        return {"agent_id": "agent-1"}

    async def discover(self, parameters):
        """Return an empty discovery response."""

        del parameters
        return {"items": []}

    async def deregister(self, **kwargs):
        """Return a deterministic deregistration response."""

        del kwargs
        return {"status": "DEREGISTERED"}

    async def close(self):
        """Close the stub connector."""


def _write_configuration(root: Path) -> Path:
    """Create a complete external configuration under one runtime root."""

    config = root / "config" / "application.conf"
    config.parent.mkdir(parents=True)
    config.write_text(
        """[runtime.application]
name = file-agent

[runtime.server]
host = 0.0.0.0
port = 8100
ssl_certificate_file = certs/server.crt
ssl_private_key_file = secrets/server.key

[runtime.nebula]
base_url = https://nebula.example
ca_file = trust/root-ca.crt

[runtime.plugins]
health = false
rest = false
""",
        encoding="utf-8",
    )
    return config


def test_layered_settings_follow_documented_precedence(tmp_path: Path) -> None:
    """CLI overrides environment, which overrides file and built-in defaults."""

    config = _write_configuration(tmp_path)
    settings = StandaloneRuntimeSettings.from_sources(
        config_path=config,
        runtime_home=tmp_path,
        environment={
            "AGENT_RUNTIME__APPLICATION__NAME": "environment-agent",
            "AGENT_RUNTIME__SERVER__PORT": "8200",
        },
        command_line={
            "application.name": "cli-agent",
            "server.port": 8300,
        },
    )

    assert settings.application.name == "cli-agent"
    assert settings.server.port == 8300
    assert settings.server.host == "0.0.0.0"
    assert settings.plugins.health is False
    assert (
        settings.server.ssl_certificate_file
        == (tmp_path / "certs/server.crt").resolve()
    )


def test_runtime_home_selects_conventional_configuration(tmp_path: Path) -> None:
    """AGENT_RUNTIME_HOME selects the conventional external config path."""

    _write_configuration(tmp_path)
    settings = StandaloneRuntimeSettings.from_sources(
        environment={"AGENT_RUNTIME_HOME": str(tmp_path)}
    )

    assert settings.application.runtime_root == tmp_path.resolve()
    assert (
        RuntimeHome.resolve(
            environment={"AGENT_RUNTIME_HOME": str(tmp_path)}
        ).config_file()
        == (tmp_path / "config/application.conf").resolve()
    )


def test_environment_override_parser_preserves_typed_values() -> None:
    """Double-underscore environment paths parse booleans and numbers."""

    values = environment_overrides(
        {
            "AGENT_RUNTIME__SERVER__PORT": "8443",
            "AGENT_RUNTIME__PLUGINS__A2A": "false",
            "UNRELATED": "ignored",
        }
    )

    assert values == {"server": {"port": 8443}, "plugins": {"a2a": False}}


def test_file_secret_provider_prevents_escape_and_empty_values(
    tmp_path: Path,
) -> None:
    """File-backed secrets stay inside their configured root."""

    secret_root = tmp_path / "secrets"
    secret_root.mkdir()
    (secret_root / "api-key").write_text("secret-value\n", encoding="utf-8")
    provider = FileSecretProvider(secret_root)

    assert provider.read_text("api-key") == "secret-value"
    with pytest.raises(ConfigurationError, match="escapes"):
        provider.read_text("../outside")


def test_explicitly_enabled_plugin_requires_components() -> None:
    """Preset composition fails closed for an unavailable enabled capability."""

    context = RuntimeContext(
        nebula=StubNebulaConnector(),
        state_store=MemoryStateStore(),
        events=NullEventSink(),
    )

    with pytest.raises(ConfigurationError, match="health.*components are absent"):
        build_embedded_runtime(
            context=context,
            components=RuntimeFeatureComponents.create(),
            options=EmbeddedPresetOptions(
                app=FastAPI(),
                plugins=RuntimePluginSettings(health=True),
            ),
        )
