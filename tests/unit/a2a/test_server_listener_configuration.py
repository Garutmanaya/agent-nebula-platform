"""Tests for A2A server listener TLS configuration."""

from pathlib import Path

import pytest

from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.protocols.a2a.server.configuration.listener import (
    A2AListenerConfigurationLoader,
)


def test_server_tls_disabled_by_default(tmp_path: Path) -> None:
    path = tmp_path / "a2aserver.conf"
    path.write_text("[server]\nhost='127.0.0.1'\nport=9000\n", encoding="utf-8")

    listener = A2AListenerConfigurationLoader().load(path)

    assert listener.tls.enabled is False
    assert listener.tls.certificate_file is None


def test_server_tls_loads_nested_configuration(tmp_path: Path) -> None:
    path = tmp_path / "a2aserver.conf"
    path.write_text(
        """
[server]
host = "127.0.0.1"
port = 9000

[server.tls]
enabled = true
trust_bundle = "ca.pem"
certificate_file = "server.crt"
private_key_file = "server.key"
""",
        encoding="utf-8",
    )

    listener = A2AListenerConfigurationLoader().load(path)

    assert listener.tls.enabled is True
    assert listener.tls.trust_bundle == (tmp_path / "ca.pem").resolve()
    assert listener.tls.certificate_file == (tmp_path / "server.crt").resolve()
    assert listener.tls.private_key_file == (tmp_path / "server.key").resolve()


def test_server_tls_requires_certificate_and_key_when_enabled(tmp_path: Path) -> None:
    path = tmp_path / "a2aserver.conf"
    path.write_text(
        "[server]\n[server.tls]\nenabled=true\ncertificate_file='server.crt'\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="configured together"):
        A2AListenerConfigurationLoader().load(path)


def test_server_tls_rejects_material_when_disabled(tmp_path: Path) -> None:
    path = tmp_path / "a2aserver.conf"
    path.write_text(
        "[server]\n[server.tls]\nenabled=false\ntrust_bundle='ca.pem'\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="enabled = true"):
        A2AListenerConfigurationLoader().load(path)
