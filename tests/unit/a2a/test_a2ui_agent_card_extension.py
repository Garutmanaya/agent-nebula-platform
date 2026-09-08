"""A2UI v1.0 Agent Card extension shape."""

from a2a.types import AgentCapabilities, AgentCard, AgentInterface
from google.protobuf.json_format import MessageToDict

from agent_nebula_platform.protocols.a2a.extensions.a2ui import (
    A2UI_EXTENSION_URI,
    ensure_a2ui_extension,
)


def test_a2ui_v1_agent_capabilities_are_version_namespaced() -> None:
    card = AgentCard(
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
        capabilities=AgentCapabilities(),
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=[],
    )

    ensure_a2ui_extension(
        card,
        supported_catalog_ids=("urn:test:catalog",),
        accepts_inline_catalogs=True,
    )

    extension = next(e for e in card.capabilities.extensions if e.uri == A2UI_EXTENSION_URI)
    assert MessageToDict(extension.params) == {
        "v1.0": {
            "supportedCatalogIds": ["urn:test:catalog"],
            "acceptsInlineCatalogs": True,
        }
    }
