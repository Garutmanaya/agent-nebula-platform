"""Tests for the Agent Nebula deterministic A2A skill-selection extension."""

from __future__ import annotations

import pytest
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from google.protobuf.json_format import MessageToDict

from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.protocols.a2a.extensions import (
    NEBULA_SKILL_SELECTION_EXTENSION_URI,
    build_skill_selection_metadata,
    ensure_skill_selection_extension,
    require_supported_skill,
    selected_skill_id,
)


def _card() -> AgentCard:
    return AgentCard(
        name="Travel Agent",
        description="Travel",
        version="1.0.0",
        supported_interfaces=[
            AgentInterface(
                url="https://travel.example/a2a",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        capabilities=AgentCapabilities(),
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=[
            AgentSkill(
                id="travel.search_flights",
                name="Search flights",
                description="Search flights",
                tags=["travel"],
            ),
            AgentSkill(
                id="travel.book_flight",
                name="Book flight",
                description="Book a flight",
                tags=["travel"],
            ),
        ],
    )


def test_extension_metadata_uses_uri_namespace() -> None:
    metadata = MessageToDict(build_skill_selection_metadata("travel.search_flights"))

    assert metadata == {
        NEBULA_SKILL_SELECTION_EXTENSION_URI: {
            "skillId": "travel.search_flights"
        }
    }


def test_selected_skill_requires_activation() -> None:
    metadata = MessageToDict(build_skill_selection_metadata("travel.search_flights"))

    assert selected_skill_id(metadata=metadata, requested_extensions=set()) is None
    assert selected_skill_id(
        metadata=metadata,
        requested_extensions={NEBULA_SKILL_SELECTION_EXTENSION_URI},
    ) == "travel.search_flights"


def test_agent_card_declares_required_extension_for_multi_skill() -> None:
    card = _card()

    ensure_skill_selection_extension(card, required=True)

    extension = card.capabilities.extensions[0]
    assert extension.uri == NEBULA_SKILL_SELECTION_EXTENSION_URI
    assert extension.required is True


def test_client_selection_must_reference_advertised_skill() -> None:
    card = _card()
    ensure_skill_selection_extension(card, required=True)

    require_supported_skill(card, "travel.search_flights")
    with pytest.raises(ConfigurationError, match="not advertised"):
        require_supported_skill(card, "travel.cancel_flight")
