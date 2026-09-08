"""Focused tests for the isolated A2A server result mapping boundary."""

from google.protobuf.json_format import MessageToDict

from agent_nebula_platform.a2ui import A2UIMessage, A2UISurface
from agent_nebula_platform.protocols.a2a.server.result_mapper import A2AResultMapper
from agent_nebula_platform.skills import SkillResult


def _surface() -> A2UISurface:
    return A2UISurface(
        surface_id="main",
        messages=(
            A2UIMessage(
                document={
                    "version": "v1.0",
                    "createSurface": {
                        "surfaceId": "main",
                        "catalogId": "urn:test:catalog",
                    },
                }
            ),
        ),
    )


def test_mapping_result_preserves_structured_business_data() -> None:
    message = A2AResultMapper().map({"message": "ready", "count": 3})

    assert message.parts[0].text == "ready"
    assert MessageToDict(message.parts[1].data) == {"message": "ready", "count": 3.0}


def test_skill_result_keeps_business_data_metadata_and_a2ui_separate() -> None:
    message = A2AResultMapper().map(
        SkillResult(
            data={"status": "ready", "count": 3},
            metadata={"requestId": "req-1"},
            ui=_surface(),
        )
    )

    assert len(message.parts) == 2
    assert MessageToDict(message.parts[0].data) == {"status": "ready", "count": 3.0}
    assert MessageToDict(message.parts[1].data) == [
        {
            "version": "v1.0",
            "createSurface": {
                "surfaceId": "main",
                "catalogId": "urn:test:catalog",
            },
        }
    ]
    assert MessageToDict(message.parts[1].metadata) == {
        "mimeType": "application/a2ui+json"
    }
    assert MessageToDict(message.metadata) == {"requestId": "req-1"}
