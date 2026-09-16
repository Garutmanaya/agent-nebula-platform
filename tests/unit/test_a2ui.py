"""A2UI surface validation and action dispatch tests."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from agent_nebula_platform.a2ui import (
    A2UIActionBinding,
    A2UIActionRequest,
    A2UIComponentPolicy,
    A2UIMessage,
    A2UIService,
    A2UISurface,
)
from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.skills import (
    SkillDefinition,
    SkillInvocationService,
    SkillRegistry,
    SkillResult,
)


def _surface(*, component: str = "Text") -> A2UISurface:
    return A2UISurface(
        surface_id="main",
        messages=(
            A2UIMessage(
                document={
                    "version": "v1.0",
                    "createSurface": {
                        "surfaceId": "main",
                        "catalogId": "urn:agent-nebula:a2ui:basic",
                    },
                }
            ),
            A2UIMessage(
                document={
                    "version": "v1.0",
                    "updateComponents": {
                        "surfaceId": "main",
                        "components": [
                            {"id": "root", "component": component, "text": "Hello"}
                        ],
                    },
                }
            ),
        ),
    )


def test_surface_serializes_to_a2a_data_part() -> None:
    service = A2UIService(
        component_policy=A2UIComponentPolicy(allowed_components=("Text",)),
        invocation_service=SkillInvocationService(registry=SkillRegistry()),
    )

    data_part = service.data_part(_surface())

    assert data_part.metadata == {"mimeType": "application/a2ui+json"}
    assert data_part.data[0]["createSurface"]["surfaceId"] == "main"


def test_surface_rejects_unapproved_component_and_executable_content() -> None:
    policy = A2UIComponentPolicy(allowed_components=("Text",))
    with pytest.raises(ConfigurationError, match="not approved"):
        policy.validate_surface(_surface(component="WebView"))

    unsafe = A2UISurface(
        surface_id="main",
        messages=(
            A2UIMessage(
                document={
                    "version": "v1.0",
                    "createSurface": {
                        "surfaceId": "main",
                        "catalogId": "urn:test",
                        "script": "alert(1)",
                    },
                }
            ),
        ),
    )
    with pytest.raises(ConfigurationError, match="prohibited executable"):
        policy.validate_surface(unsafe)


@pytest.mark.asyncio
async def test_action_dispatch_uses_existing_skill_boundary() -> None:
    async def submit(invocation):
        return SkillResult(data={"received": invocation.payload["context"]})

    invocation = SkillInvocationService(
        registry=SkillRegistry(
            (SkillDefinition(skill_id="booking.submit", handler=submit),)
        )
    )
    service = A2UIService(
        component_policy=A2UIComponentPolicy(allowed_components=("Button",)),
        invocation_service=invocation,
        action_bindings=(
            A2UIActionBinding(action_name="submit_booking", skill_id="booking.submit"),
        ),
    )

    result = await service.dispatch_action(
        action=A2UIActionRequest(
            name="submit_booking",
            surface_id="main",
            context={"flight_id": "F100"},
        ),
        access_token=None,
        dpop_proof=None,
        http_method="POST",
        target_uri="https://agent.example/api/v1/a2ui/actions",
    )

    assert result.data == {"received": {"flight_id": "F100"}}


def test_action_request_preserves_response_options() -> None:
    """A2UI action response options survive the transport-neutral model boundary."""

    action = A2UIActionRequest(
        name="parking.space.hold",
        surface_id="parking-main",
        source_component_id="L1-A-01",
        timestamp=datetime.now(timezone.utc),
        want_response=True,
        action_id="action-123",
    )

    assert action.want_response is True
    assert action.action_id == "action-123"
