"""A2UI surface serialization, negotiation, and protected action dispatch."""

from __future__ import annotations

from .models import (
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
        protocol_policy: A2UIProtocolPolicy | None = None,
    ) -> None:
        self._component_policy = component_policy
        self._protocol_policy = protocol_policy or A2UIProtocolPolicy()

    def capabilities(self) -> A2UICapabilities:
        """Return the immutable renderer-facing contract of this runtime."""

        return A2UICapabilities(
            supported_versions=self._protocol_policy.supported_versions,
            preferred_version=self._protocol_policy.preferred_version,
            allowed_components=self._component_policy.allowed_components,
            allowed_functions=self._component_policy.allowed_functions,
            action_names=(),
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
        self._component_policy.validate_surface(surface)
        return A2UIDataPart(
            data=tuple(message.copy_document() for message in surface.messages)
        )
