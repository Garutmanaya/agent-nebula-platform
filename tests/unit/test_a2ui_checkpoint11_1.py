"""Checkpoint 11.1 A2UI protocol, catalog, and binding validation tests."""

from __future__ import annotations

import pytest

from agent_nebula_platform.a2ui import (
    A2UIActionBinding,
    A2UIActionRequest,
    A2UIComponentPolicy,
    A2UIMessage,
    A2UIProtocolPolicy,
    A2UIRendererCapabilities,
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


def _surface(
    *,
    version: str = "v1.0",
    catalog_id: str = "urn:agent-nebula:a2ui:test",
    components: list[dict[str, object]] | None = None,
) -> A2UISurface:
    """Build a small surface that exercises references and actions."""

    return A2UISurface(
        surface_id="main",
        messages=(
            A2UIMessage(
                document={
                    "version": version,
                    "createSurface": {
                        "surfaceId": "main",
                        "catalogId": catalog_id,
                    },
                }
            ),
            A2UIMessage(
                document={
                    "version": version,
                    "updateComponents": {
                        "surfaceId": "main",
                        "components": components
                        or [
                            {
                                "id": "root",
                                "component": "Column",
                                "children": ["submit"],
                            },
                            {
                                "id": "submit",
                                "component": "Button",
                                "text": "Submit",
                                "action": {"event": {"name": "submit"}},
                            },
                        ],
                    },
                }
            ),
        ),
    )


def _service() -> A2UIService:
    """Create one service with an action mapped to a registered skill."""

    async def submit(_invocation):
        return SkillResult(data={"submitted": True})

    return A2UIService(
        component_policy=A2UIComponentPolicy(
            allowed_components=("Column", "Button"),
        ),
        protocol_policy=A2UIProtocolPolicy(
            supported_versions=("v1.0",),
            preferred_version="v1.0",
            allowed_catalog_ids=("urn:agent-nebula:a2ui:test",),
        ),
        invocation_service=SkillInvocationService(
            registry=SkillRegistry(
                (SkillDefinition(skill_id="submit.skill", handler=submit),)
            )
        ),
        action_bindings=(
            A2UIActionBinding(action_name="submit", skill_id="submit.skill"),
        ),
    )


def test_capabilities_and_negotiation_are_explicit() -> None:
    """Runtime exposes one stable contract and negotiates the common subset."""

    service = _service()

    capabilities = service.capabilities()
    negotiated = service.negotiate(
        A2UIRendererCapabilities(
            supported_versions=("v1.0",),
            supported_components=("Button", "Text"),
            supported_functions=(),
        )
    )

    assert capabilities.preferred_version == "v1.0"
    assert capabilities.action_names == ("submit",)
    assert negotiated.version == "v1.0"
    assert negotiated.components == ("Button",)


def test_negotiation_fails_when_versions_do_not_overlap() -> None:
    """A renderer cannot silently downgrade to an unsupported wire contract."""

    with pytest.raises(ConfigurationError, match="no common A2UI version"):
        _service().negotiate(
            A2UIRendererCapabilities(
                supported_versions=("v2.0",),
            )
        )


def test_surface_rejects_mixed_versions_and_unapproved_catalog() -> None:
    """One surface stream uses one supported version and approved catalog."""

    mixed = A2UISurface(
        surface_id="main",
        messages=(
            A2UIMessage(
                document={
                    "version": "v1.0",
                    "createSurface": {
                        "surfaceId": "main",
                        "catalogId": "urn:agent-nebula:a2ui:test",
                    },
                }
            ),
            A2UIMessage(
                document={
                    "version": "v0.9.1",
                    "deleteSurface": {"surfaceId": "main"},
                }
            ),
        ),
    )

    with pytest.raises(ConfigurationError, match="must use one version"):
        _service().data_part(mixed)

    with pytest.raises(ConfigurationError, match="catalog is not approved"):
        _service().data_part(_surface(catalog_id="urn:untrusted"))


def test_surface_accepts_v1_dynamic_child_list_template() -> None:
    """A2UI v1.0 ChildList templates contribute their componentId reference."""

    surface = _surface(
        components=[
            {
                "id": "root",
                "component": "Column",
                "children": {
                    "componentId": "result_template",
                    "path": "/items",
                },
            },
            {
                "id": "result_template",
                "component": "Button",
                "text": "Select",
                "action": {"event": {"name": "submit"}},
            },
        ]
    )

    _service().data_part(surface)


def test_surface_rejects_invalid_v1_dynamic_child_list_template() -> None:
    """Dynamic ChildList templates require both componentId and data path."""

    surface = _surface(
        components=[
            {
                "id": "root",
                "component": "Column",
                "children": {"componentId": "result_template"},
            },
            {"id": "result_template", "component": "Button", "text": "Select"},
        ]
    )

    with pytest.raises(ConfigurationError, match="requires componentId and path"):
        _service().data_part(surface)


def test_surface_rejects_unresolved_component_references() -> None:
    """Renderer references must resolve within the complete surface stream."""

    surface = _surface(
        components=[
            {
                "id": "root",
                "component": "Column",
                "children": ["missing"],
            }
        ]
    )

    with pytest.raises(ConfigurationError, match="references are unresolved"):
        _service().data_part(surface)


def test_surface_rejects_unregistered_action_names() -> None:
    """A surface cannot dispatch to an action absent from the binding registry."""

    surface = _surface(
        components=[
            {
                "id": "root",
                "component": "Button",
                "action": {"event": {"name": "delete_everything"}},
            }
        ]
    )

    with pytest.raises(ConfigurationError, match="unregistered actions"):
        _service().data_part(surface)


@pytest.mark.asyncio
async def test_action_version_is_validated_before_skill_dispatch() -> None:
    """Renderer actions outside the negotiated protocol fail before invocation."""

    with pytest.raises(ConfigurationError, match="action version is not supported"):
        await _service().dispatch_action(
            action=A2UIActionRequest(
                version="v2.0",
                name="submit",
                surface_id="main",
            ),
            access_token=None,
            dpop_proof=None,
            http_method="POST",
            target_uri="https://agent.example/api/v1/a2ui/actions",
        )


def test_v1_create_surface_validates_embedded_components_and_actions() -> None:
    """v1.0 single-message surfaces use the same component/action policy."""

    surface = A2UISurface(
        surface_id="main",
        messages=(
            A2UIMessage(
                document={
                    "version": "v1.0",
                    "createSurface": {
                        "surfaceId": "main",
                        "catalogId": "urn:agent-nebula:a2ui:test",
                        "components": [
                            {
                                "id": "root",
                                "component": "Button",
                                "action": {"event": {"name": "submit"}},
                            }
                        ],
                        "dataModel": {"ready": True},
                    },
                }
            ),
        ),
    )

    data_part = _service().data_part(surface)

    assert data_part.data[0]["createSurface"]["dataModel"] == {"ready": True}


def test_v1_agent_rpc_envelopes_are_preserved() -> None:
    """v1.0 agent RPC messages remain opaque until the RPC layer owns them."""

    call = A2UIMessage(
        document={
            "version": "v1.0",
            "callRendererFunction": {
                "functionCallId": "call-1",
                "callFunction": {"call": "clipboard.copy", "args": {}},
            },
        }
    )
    response = A2UIMessage(
        document={
            "version": "v1.0",
            "agentFunctionResponse": {
                "functionCallId": "call-2",
                "value": {"ok": True},
            },
        }
    )

    assert call.message_type == "callRendererFunction"
    assert response.message_type == "agentFunctionResponse"


def test_v1_agent_message_rejects_unknown_top_level_fields() -> None:
    """v1.0 envelopes contain only version and one defined message type."""

    with pytest.raises(ValueError, match="unsupported top-level fields"):
        A2UIMessage(
            document={
                "version": "v1.0",
                "createSurface": {"surfaceId": "main"},
                "legacyExtension": {},
            }
        )
