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
    version: str = "v0.9.1",
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
                                "action": {"name": "submit"},
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
            supported_versions=("v0.9.1",),
            preferred_version="v0.9.1",
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
            supported_versions=("v1.0", "v0.9.1"),
            supported_components=("Button", "Text"),
            supported_functions=(),
        )
    )

    assert capabilities.preferred_version == "v0.9.1"
    assert capabilities.action_names == ("submit",)
    assert negotiated.version == "v0.9.1"
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
                    "version": "v0.9.1",
                    "createSurface": {
                        "surfaceId": "main",
                        "catalogId": "urn:agent-nebula:a2ui:test",
                    },
                }
            ),
            A2UIMessage(
                document={
                    "version": "v1.0",
                    "deleteSurface": {"surfaceId": "main"},
                }
            ),
        ),
    )

    with pytest.raises(ConfigurationError, match="must use one version"):
        _service().data_part(mixed)

    with pytest.raises(ConfigurationError, match="catalog is not approved"):
        _service().data_part(_surface(catalog_id="urn:untrusted"))


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
                "action": {"name": "delete_everything"},
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
