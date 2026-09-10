"""Unit tests for embedded and standalone preset composition."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_nebula_platform import MemoryStateStore, NullEventSink, RuntimeContext
from agent_nebula_platform.platform.health import StaticHealthProvider
from agent_nebula_platform.platform.presets import (
    EmbeddedPresetOptions,
    RuntimeApplicationSettings,
    RuntimeFeatureComponents,
    StandaloneRuntimeSettings,
    build_embedded_runtime,
)


class StubNebulaConnector:
    """Minimal connector used to verify preset composition without network I/O."""

    async def resolve_onboarding(self, payload):
        """Return no resolved registration."""

        del payload

    async def onboard(self, payload):
        """Return a stable registration document."""

        del payload
        return {"agent_id": "agent-1"}

    async def discover(self, parameters):
        """Return an empty discovery result."""

        del parameters
        return {"items": []}

    async def deregister(self, **kwargs):
        """Return a stable lifecycle response."""

        del kwargs
        return {"status": "DEREGISTERED"}

    async def close(self):
        """Close the stub connector."""


def test_embedded_preset_attaches_health_routes() -> None:
    """Embedded composition attaches routes without starting a server."""

    app = FastAPI()
    context = RuntimeContext(
        nebula=StubNebulaConnector(),
        state_store=MemoryStateStore(),
        events=NullEventSink(),
    )
    runtime = build_embedded_runtime(
        context=context,
        components=RuntimeFeatureComponents.create(
            health=StaticHealthProvider(),
        ),
        options=EmbeddedPresetOptions(app=app),
    )

    assert runtime.context is context
    # Route attachment occurs at runtime initialization so plugin ordering and
    # failures remain visible through the standard runtime lifecycle.
    import asyncio

    asyncio.run(runtime.initialize())
    try:
        with TestClient(app) as client:
            response = client.get("/health")
            live = client.get("/health/live")
            ready = client.get("/health/ready")

        assert response.status_code == 200
        assert response.json()["ready"] is True
        assert live.status_code == 200
        assert ready.status_code == 200
    finally:
        asyncio.run(runtime.close())


def test_standalone_settings_resolve_relative_paths(tmp_path: Path) -> None:
    """Standalone paths are normalized once against the configured root."""

    settings = StandaloneRuntimeSettings.model_validate(
        {
            "application": {
                "name": "demo-agent",
                "runtime_root": str(tmp_path),
            },
            "server": {
                "ssl_certificate_file": "certs/server.crt",
                "ssl_private_key_file": "certs/server.key",
            },
            "nebula": {
                "base_url": "https://nebula.example",
                "ca_file": "trust/root-ca.crt",
            },
        }
    ).resolve_paths()

    assert (
        settings.server.ssl_certificate_file
        == (tmp_path / "certs/server.crt").resolve()
    )
    assert settings.nebula.ca_file == (tmp_path / "trust/root-ca.crt").resolve()
    assert settings.state.directory == (tmp_path / "runtime/state").resolve()


def test_standalone_settings_reject_path_escape(tmp_path: Path) -> None:
    """Standalone managed paths cannot escape the configured product root."""

    settings = StandaloneRuntimeSettings.model_validate(
        {
            "application": {
                "name": "demo-agent",
                "runtime_root": str(tmp_path),
            },
            "server": {
                "ssl_certificate_file": "../outside.crt",
                "ssl_private_key_file": "certs/server.key",
            },
            "nebula": {
                "base_url": "https://nebula.example",
                "ca_file": "trust/root-ca.crt",
            },
        }
    )

    import pytest

    with pytest.raises(ValueError, match="escapes configured runtime root"):
        settings.resolve_paths()


def test_standalone_preset_builds_managed_app(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Standalone composition creates an app without contacting Agent Nebula."""

    import ssl

    from agent_nebula_platform.platform.presets import build_standalone_agent
    from agent_nebula_platform.platform.tls import FileTlsContextProvider

    monkeypatch.setattr(
        FileTlsContextProvider,
        "create_client_context",
        lambda self: ssl.create_default_context(),
    )
    settings = StandaloneRuntimeSettings.model_validate(
        {
            "application": {
                "name": "managed-demo",
                "runtime_root": str(tmp_path),
            },
            "server": {
                "ssl_certificate_file": "certs/server.crt",
                "ssl_private_key_file": "certs/server.key",
            },
            "nebula": {
                "base_url": "https://nebula.example",
                "ca_file": "trust/root-ca.crt",
            },
            "logging": {"console_enabled": False},
        }
    )

    agent = build_standalone_agent(
        settings=settings,
        components=RuntimeFeatureComponents.create(
            health=StaticHealthProvider(),
        ),
    )

    assert agent.app.title == "managed-demo"
    assert agent.settings.state.directory == (tmp_path / "runtime/state").resolve()

    import asyncio

    asyncio.run(agent.runtime.initialize())
    try:
        with TestClient(agent.app) as client:
            response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["ready"] is True
    finally:
        asyncio.run(agent.runtime.close())


def test_state_directory_may_live_under_product_root(tmp_path: Path) -> None:
    """Replaceable containers may persist runtime identity under product state."""

    config = tmp_path / "application.conf"
    runtime_root = tmp_path / "runtime/agent-1"
    product_root = tmp_path / "product"
    state_root = product_root / "data/registrations/showcase/fleet/agent-1"
    config.write_text(
        f"""
[runtime.application]
name = agent-1
runtime_root = {runtime_root}
product_root = {product_root}
role_profile = PROVIDER

[runtime.server]
host = 127.0.0.1
port = 8101
tls_enabled = false

[runtime.nebula]
base_url = https://nebula.example
ca_file = {tmp_path / "ca.pem"}

[runtime.state]
directory = {state_root}

[runtime.plugins]
onboarding = false
""",
        encoding="utf-8",
    )

    settings = RuntimeApplicationSettings.from_ini(config).effective_runtime()

    assert settings.state.directory == state_root.resolve()
