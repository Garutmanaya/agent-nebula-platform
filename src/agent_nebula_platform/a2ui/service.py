"""A2UI surface serialization, negotiation, and protected action dispatch."""

from __future__ import annotations

from collections.abc import Iterable

from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.skills import SkillInvocationService, SkillResult

from .models import (
    A2UIActionBinding,
    A2UIActionRequest,
    A2UICapabilities,
    A2UIDataPart,
    A2UINegotiatedCapabilities,
    A2UIRendererCapabilities,
    A2UISurface,
)
from .validation import A2UIComponentPolicy, A2UIProtocolPolicy


class A2UIService:
    """Validate surfaces, negotiate contracts, and dispatch renderer actions."""

    def __init__(
        self,
        *,
        component_policy: A2UIComponentPolicy,
        invocation_service: SkillInvocationService,
        protocol_policy: A2UIProtocolPolicy | None = None,
        action_bindings: Iterable[A2UIActionBinding] = (),
    ) -> None:
        self._component_policy = component_policy
        self._protocol_policy = protocol_policy or A2UIProtocolPolicy()
        self._invocation = invocation_service
        self._bindings: dict[str, str] = {}
        for binding in action_bindings:
            if binding.action_name in self._bindings:
                raise ConfigurationError(
                    f"A2UI action binding is duplicated: {binding.action_name}"
                )
            self._bindings[binding.action_name] = binding.skill_id

    def capabilities(self) -> A2UICapabilities:
        """Return the immutable renderer-facing contract of this runtime."""

        return A2UICapabilities(
            supported_versions=self._protocol_policy.supported_versions,
            preferred_version=self._protocol_policy.preferred_version,
            allowed_components=self._component_policy.allowed_components,
            allowed_functions=self._component_policy.allowed_functions,
            action_names=tuple(sorted(self._bindings)),
        )

    def negotiate(
        self,
        renderer: A2UIRendererCapabilities,
    ) -> A2UINegotiatedCapabilities:
        """Select one mutually supported version and approved catalog subset."""

        version = self._protocol_policy.negotiate(renderer.supported_versions)
        renderer_components = frozenset(renderer.supported_components)
        renderer_functions = frozenset(renderer.supported_functions)
        return A2UINegotiatedCapabilities(
            version=version,
            components=tuple(
                value
                for value in self._component_policy.allowed_components
                if value in renderer_components
            ),
            functions=tuple(
                value
                for value in self._component_policy.allowed_functions
                if value in renderer_functions
            ),
        )

    def data_part(self, surface: A2UISurface) -> A2UIDataPart:
        """Validate and serialize one surface into an A2A-compatible DataPart."""

        self._protocol_policy.validate_surface(surface)
        action_names = self._component_policy.validate_surface(surface)
        unknown_actions = sorted(set(action_names) - set(self._bindings))
        if unknown_actions:
            raise ConfigurationError(
                f"A2UI surface declares unregistered actions: {unknown_actions}"
            )
        return A2UIDataPart(
            data=tuple(message.copy_document() for message in surface.messages)
        )

    async def dispatch_action(
        self,
        *,
        action: A2UIActionRequest,
        access_token: str | None,
        dpop_proof: str | None,
        http_method: str,
        target_uri: str,
        nonce_context: str | None = None,
    ) -> SkillResult:
        """Route one event to its declared skill through the common security boundary."""

        self._protocol_policy.validate_action(action)
        skill_id = self._bindings.get(action.name)
        if skill_id is None:
            raise ConfigurationError(f"A2UI action is not registered: {action.name}")
        payload = {
            "surface_id": action.surface_id,
            "source_component_id": action.source_component_id,
            "context": dict(action.context),
            "data_model": dict(action.data_model),
        }
        return await self._invocation.invoke(
            skill_id=skill_id,
            payload=payload,
            access_token=access_token,
            dpop_proof=dpop_proof,
            http_method=http_method,
            target_uri=target_uri,
            nonce_context=nonce_context,
        )
