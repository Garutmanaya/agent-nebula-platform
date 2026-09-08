"""Focused tests for A2UI v1.0 client negotiation and response parsing."""

from a2a.types import AgentCapabilities, AgentCard, AgentExtension, AgentInterface, AgentSkill
from google.protobuf.json_format import MessageToDict

from agent_nebula_platform.a2ui.configuration import A2UIConfiguration
from agent_nebula_platform.protocols.a2a.client.extension_context import (
    A2AClientExtensionContextBuilder,
)
from agent_nebula_platform.protocols.a2a.extensions.a2ui import (
    A2UIClientExtension,
    A2UI_EXTENSION_URI,
    A2UIResponseParser,
)
from agent_nebula_platform.protocols.a2a.extensions.skill_selection import (
    NEBULA_SKILL_SELECTION_EXTENSION_URI,
    SkillSelectionClientExtension,
)


def _card() -> AgentCard:
    # Only fields relevant to extension negotiation are used by these tests.
    return AgentCard(
        name="test",
        description="test",
        version="1.0.0",
        supported_interfaces=[
            AgentInterface(
                url="https://test.example/a2a",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        capabilities=AgentCapabilities(
            extensions=[
                AgentExtension(uri=A2UI_EXTENSION_URI, required=False),
                AgentExtension(
                    uri=NEBULA_SKILL_SELECTION_EXTENSION_URI, required=False
                ),
            ]
        ),
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=[
            AgentSkill(
                id="hello",
                name="Hello",
                description="Hello",
                tags=["test"],
            )
        ],
    )


def test_a2ui_contributes_renderer_capabilities_to_message_metadata() -> None:
    extension = A2UIClientExtension(
        A2UIConfiguration(
            enabled=True,
            supported_catalog_ids=("urn:test:catalog",),
        )
    )
    context = A2AClientExtensionContextBuilder((extension,)).build(_card())

    assert MessageToDict(context.message_metadata) == {
        "a2uiRendererCapabilities": {
            "v1.0": {"supportedCatalogIds": ["urn:test:catalog"]}
        }
    }
    assert context.call_context is not None


def test_disabled_a2ui_contributes_nothing() -> None:
    extension = A2UIClientExtension(A2UIConfiguration(enabled=False))
    context = A2AClientExtensionContextBuilder((extension,)).build(_card())

    assert context.call_context is None
    assert context.message_metadata is None


def test_response_parser_extracts_a2ui_without_changing_other_parts() -> None:
    responses = (
        {
            "message": {
                "parts": [
                    {"text": "ready"},
                    {
                        "data": [
                            {
                                "version": "v1.0",
                                "createSurface": {
                                    "surfaceId": "main",
                                    "catalogId": "urn:test:catalog",
                                },
                            }
                        ],
                        "metadata": {"mimeType": "application/a2ui+json"},
                    },
                ]
            }
        },
    )

    parts = A2UIResponseParser().parse(responses)

    assert len(parts) == 1
    assert parts[0].data[0]["version"] == "v1.0"
    assert responses[0]["message"]["parts"][0] == {"text": "ready"}


def test_a2ui_and_skill_selection_contributions_coexist() -> None:
    context = A2AClientExtensionContextBuilder(
        (
            SkillSelectionClientExtension(),
            A2UIClientExtension(
                A2UIConfiguration(
                    enabled=True, supported_catalog_ids=("urn:test:catalog",)
                )
            ),
        )
    ).build(_card(), skill_id="hello")

    assert context.call_context is not None
    assert context.call_context.state["agent_nebula.a2a.skill_id"] == "hello"
    assert MessageToDict(context.request_metadata) == {
        NEBULA_SKILL_SELECTION_EXTENSION_URI: {"skillId": "hello"}
    }
    assert "a2uiRendererCapabilities" in MessageToDict(context.message_metadata)


def test_a2ui_enabled_falls_back_when_remote_card_does_not_advertise_it() -> None:
    card = _card()
    del card.capabilities.extensions[0]
    extension = A2UIClientExtension(
        A2UIConfiguration(enabled=True, supported_catalog_ids=("urn:test:catalog",))
    )

    context = A2AClientExtensionContextBuilder((extension,)).build(card)

    assert context.call_context is None
    assert context.message_metadata is None
