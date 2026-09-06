"""Regression tests for ingress-terminated TLS deployments."""

from pathlib import Path

from agent_nebula_platform.platform.presets.standalone.settings import (
    StandaloneServerSettings,
)


def test_server_settings_allow_http_without_certificate_files() -> None:
    """Internal listeners may use HTTP when an ingress terminates TLS."""

    settings = StandaloneServerSettings(tls_enabled=False)
    assert settings.ssl_certificate_file is None
    assert settings.ssl_private_key_file is None


def test_server_settings_keep_tls_files_when_enabled() -> None:
    """Direct TLS listeners still require and preserve their key pair."""

    settings = StandaloneServerSettings(
        tls_enabled=True,
        ssl_certificate_file=Path("certs/server.crt"),
        ssl_private_key_file=Path("certs/server.key"),
    )
    assert settings.tls_enabled is True
