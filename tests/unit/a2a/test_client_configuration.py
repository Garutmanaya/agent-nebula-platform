"""Tests for dedicated A2A client configuration and official client construction."""

from __future__ import annotations

from pathlib import Path

import pytest
from a2a.types import AgentCapabilities, AgentCard, AgentInterface

from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.protocols.a2a import (
    A2AClientConfigurationLoader,
    A2AClientServiceFactory,
)


class TestA2AClientConfigurationLoader:
    """Verify fail-closed local A2A client configuration."""

    def test_loads_transport_and_tls_configuration(self, tmp_path: Path) -> None:
        """Load supported bindings without embedding any remote Agent Card."""

        trust = tmp_path / "ca.pem"
        trust.write_text("test", encoding="utf-8")
        path = tmp_path / "a2aclient.conf"
        path.write_text(_configuration(trust), encoding="utf-8")

        configuration = A2AClientConfigurationLoader().load(path)

        assert configuration.supported_protocol_bindings == ("JSONRPC", "HTTP+JSON")
        assert configuration.use_client_preference is False
        assert configuration.tls.enabled is False
        assert configuration.tls.trust_bundle == trust.resolve()

    def test_rejects_unknown_transport(self, tmp_path: Path) -> None:
        """Reject bindings the official Runtime integration cannot construct."""

        trust = tmp_path / "ca.pem"
        trust.write_text("test", encoding="utf-8")
        path = tmp_path / "a2aclient.conf"
        path.write_text(
            _configuration(trust).replace('"HTTP+JSON"', '"CUSTOM"'),
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError, match="unsupported protocol bindings"):
            A2AClientConfigurationLoader().load(path)

    def test_requires_certificate_and_key_together(self, tmp_path: Path) -> None:
        """Never construct a partially configured mTLS-capable transport."""

        trust = tmp_path / "ca.pem"
        trust.write_text("test", encoding="utf-8")
        cert = tmp_path / "client.crt"
        cert.write_text("test", encoding="utf-8")
        path = tmp_path / "a2aclient.conf"
        path.write_text(
            _configuration(trust) + f'certificate_file = "{cert}"\n',
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError, match="must be configured together"):
            A2AClientConfigurationLoader().load(path)


class TestA2AClientServiceFactory:
    """Verify Runtime delegates transport selection to the official ClientFactory."""

    def test_official_factory_selects_remote_preferred_compatible_interface(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Server interface order wins when use_client_preference is disabled."""

        trust = tmp_path / "ca.pem"
        trust.write_text("test", encoding="utf-8")
        path = tmp_path / "a2aclient.conf"
        path.write_text(_configuration(trust), encoding="utf-8")
        adapter = A2AClientServiceFactory().create(path)

        # Avoid parsing a synthetic CA in this unit test; transport selection is
        # the behavior under test, not Python's TLS parser.
        import httpx

        monkeypatch.setattr(
            adapter, "_new_http_client", lambda **_: httpx.AsyncClient()
        )
        card = _agent_card()

        client = adapter.create(card)

        assert client.__class__.__module__.startswith("a2a.client")
        assert client._transport.url == "https://agent.example/rest"


def _configuration(trust: Path) -> str:
    return f'''\n[client]\nstreaming = true\npolling = false\nsupported_protocol_bindings = ["JSONRPC", "HTTP+JSON"]\nuse_client_preference = false\naccepted_output_modes = ["application/json"]\ntimeout_seconds = 15\n\n[client.tls]\ntrust_bundle = "{trust}"\n'''


def _agent_card() -> AgentCard:
    return AgentCard(
        name="Remote",
        description="Remote agent",
        version="1.0.0",
        supported_interfaces=[
            AgentInterface(
                url="https://agent.example/rest",
                protocol_binding="HTTP+JSON",
                protocol_version="1.0",
            ),
            AgentInterface(
                url="https://agent.example/rpc",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            ),
        ],
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=[],
    )


def test_client_configuration_may_use_system_ca_store(tmp_path: Path) -> None:
    """A2A clients need no private trust bundle when system trust is sufficient."""
    path = tmp_path / "a2aclient.conf"
    path.write_text(
        """
[client]
supported_protocol_bindings = ["JSONRPC"]
accepted_output_modes = ["text/plain"]

[client.tls]
enabled = true
""",
        encoding="utf-8",
    )

    configuration = A2AClientConfigurationLoader().load(path)
    assert configuration.tls.trust_bundle is None
