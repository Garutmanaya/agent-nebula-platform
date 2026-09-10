"""Tests for external A2A server configuration and official Agent Card creation."""

from __future__ import annotations

from pathlib import Path

import pytest
from a2a.types import AgentCard

from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.protocols.a2a.server.configuration import (
    A2AServerConfigurationService,
)


class TestA2AServerConfigurationService:
    """Verify fail-closed loading of A2A 1.0 Agent Card configuration."""

    def test_loads_complete_official_agent_card(self, tmp_path: Path) -> None:
        """Build official protobuf types without a parallel Runtime Agent Card model."""

        path = tmp_path / "a2aserver.conf"
        path.write_text(_VALID_CONFIGURATION, encoding="utf-8")

        configuration = A2AServerConfigurationService().load(path)
        card = configuration.agent_card

        assert isinstance(card, AgentCard)
        assert configuration.agent_card_url == (
            "https://inventory.example/.well-known/agent-card.json"
        )
        assert configuration.agent_card_route == "/.well-known/agent-card.json"
        assert card.name == "Inventory Agent"
        assert card.supported_interfaces[0].protocol_binding == "JSONRPC"
        assert (
            card.security_schemes["oauth"].WhichOneof("scheme")
            == "oauth2_security_scheme"
        )
        assert list(card.security_requirements[0].schemes["oauth"].list) == [
            "inventory.read"
        ]
        assert card.skills[0].id == "inventory.get"
        assert list(card.skills[0].security_requirements[0].schemes["oauth"].list) == [
            "inventory.read"
        ]

    def test_rejects_unknown_security_scheme_reference(self, tmp_path: Path) -> None:
        """Fail startup when a requirement references a scheme absent from the card."""

        path = tmp_path / "a2aserver.conf"
        path.write_text(
            _VALID_CONFIGURATION.replace(
                'schemes = { oauth = ["inventory.read"] }',
                'schemes = { missing = ["inventory.read"] }',
                1,
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError, match="undefined schemes"):
            A2AServerConfigurationService().load_agent_card(path)

    def test_rejects_duplicate_skill_identifiers(self, tmp_path: Path) -> None:
        """Fail startup when two advertised skills use the same A2A identifier."""

        path = tmp_path / "a2aserver.conf"
        path.write_text(
            _VALID_CONFIGURATION
            + """\n[[agent_card.skills]]\nid = "inventory.get"\nname = "Duplicate"\ndescription = "Duplicate skill"\ntags = ["duplicate"]\n""",
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError, match="must be unique"):
            A2AServerConfigurationService().load_agent_card(path)

    def test_rejects_missing_official_required_field(self, tmp_path: Path) -> None:
        """Delegate A2A REQUIRED-field validation to the official SDK utility."""

        path = tmp_path / "a2aserver.conf"
        path.write_text(
            _VALID_CONFIGURATION.replace('tags = ["inventory"]\n', ""),
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError, match="required by the A2A 1.0 model"):
            A2AServerConfigurationService().load_agent_card(path)

    def test_rejects_missing_agent_card_section(self, tmp_path: Path) -> None:
        """Fail startup when the dedicated server file does not contain an Agent Card."""

        path = tmp_path / "a2aserver.conf"
        path.write_text('[server]\nname = "not-an-agent-card"\n', encoding="utf-8")

        with pytest.raises(ConfigurationError, match=r"\[agent_card\] section"):
            A2AServerConfigurationService().load_agent_card(path)


_VALID_CONFIGURATION = """
[agent_card]
url = "https://inventory.example/.well-known/agent-card.json"
name = "Inventory Agent"
description = "Inventory provider"
version = "1.0.0"
default_input_modes = ["application/json"]
default_output_modes = ["application/json"]

[[agent_card.supported_interfaces]]
url = "https://inventory.example/a2a"
protocol_binding = "JSONRPC"
protocol_version = "1.0"

[agent_card.capabilities]
streaming = true
push_notifications = false
extended_agent_card = false

[agent_card.security_schemes.oauth.oauth2_security_scheme]
description = "Inventory OAuth"
oauth2_metadata_url = "https://auth.example/.well-known/oauth-authorization-server"

[agent_card.security_schemes.oauth.oauth2_security_scheme.flows.client_credentials]
token_url = "https://auth.example/token"
scopes = { "inventory.read" = "Read inventory" }

[[agent_card.security_requirements]]
schemes = { oauth = ["inventory.read"] }

[[agent_card.skills]]
id = "inventory.get"
name = "Get Inventory"
description = "Retrieve inventory"
tags = ["inventory"]

[[agent_card.skills.security_requirements]]
schemes = { oauth = ["inventory.read"] }
"""
