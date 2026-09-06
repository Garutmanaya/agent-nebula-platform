"""Minimal A2UI surface and action-binding composition example."""

from agent_nebula_platform.a2ui import A2UIActionBinding, A2UIMessage, A2UISurface
from agent_nebula_platform.a2ui.plugin import A2UIPlugin
from agent_nebula_platform.skills import SkillInvocation, SkillResult


async def search_flights(invocation: SkillInvocation) -> SkillResult:
    """Return deterministic business data with a declarative A2UI surface."""

    del invocation
    return SkillResult(
        data={"flights": [{"id": "F100", "price": 450}]},
        ui=A2UISurface(
            surface_id="flight-results",
            messages=(
                A2UIMessage(
                    document={
                        "version": "v0.9.1",
                        "createSurface": {
                            "surfaceId": "flight-results",
                            "catalogId": "urn:agent-nebula:a2ui:travel",
                        },
                    }
                ),
                A2UIMessage(
                    document={
                        "version": "v0.9.1",
                        "updateComponents": {
                            "surfaceId": "flight-results",
                            "components": [
                                {
                                    "id": "root",
                                    "component": "Column",
                                    "children": ["title"],
                                },
                                {
                                    "id": "title",
                                    "component": "Text",
                                    "text": "Available flights",
                                },
                            ],
                        },
                    }
                ),
            ),
        ),
    )


A2UI_PLUGIN = A2UIPlugin(
    allowed_components=("Column", "Text", "Button", "Card"),
    action_bindings=(
        A2UIActionBinding(
            action_name="select_flight",
            skill_id="flight.select",
        ),
    ),
)
