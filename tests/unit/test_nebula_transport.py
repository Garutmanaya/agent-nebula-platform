"""Unit tests for centralized Agent Nebula Registry transport composition."""

from pathlib import Path

import ssl
import pytest

from agent_nebula_platform.integrations.nebula import (
    NebulaConfiguration,
    NebulaConnectorFactory,
)
from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.platform.tls import FileTlsContextProvider


def _configuration(tmp_path: Path, *, authentication: str, api_key: str | None = None):
    ca = tmp_path / "ca.pem"
    ca.write_text("ca", encoding="utf-8")
    registration = [f"authentication={authentication}"]
    if api_key is not None:
        key = tmp_path / "api-key"
        key.write_text(api_key, encoding="utf-8")
        registration.append("api_key_file=api-key")
    conf = tmp_path / "nebula.conf"
    conf.write_text(
        "[nebula]\nbase_url=https://nebula.example\n"
        "[tls]\nmode=full-verify\nca_file=ca.pem\n"
        "[registration]\n" + "\n".join(registration) + "\n",
        encoding="utf-8",
    )
    return NebulaConfiguration.load(conf)


def _disable_real_tls(monkeypatch) -> None:
    monkeypatch.setattr(
        FileTlsContextProvider,
        "create_client_context",
        lambda self: ssl.create_default_context(),
    )


def test_connector_factory_adds_api_key_transport_header(tmp_path, monkeypatch):
    _disable_real_tls(monkeypatch)
    connector = NebulaConnectorFactory.create(
        _configuration(tmp_path, authentication="API_KEY", api_key=" secret-key \n")
    )
    assert connector._client.headers["X-API-Key"] == "secret-key"


def test_connector_factory_open_registration_has_no_api_key_header(
    tmp_path, monkeypatch
):
    _disable_real_tls(monkeypatch)
    connector = NebulaConnectorFactory.create(
        _configuration(tmp_path, authentication="OPEN")
    )
    assert "X-API-Key" not in connector._client.headers


def test_connector_factory_rejects_empty_api_key(tmp_path, monkeypatch):
    _disable_real_tls(monkeypatch)
    with pytest.raises(ConfigurationError, match="API key file is empty"):
        NebulaConnectorFactory.create(
            _configuration(tmp_path, authentication="API_KEY", api_key="  \n")
        )
