"""Security-oriented validation for declarative A2UI message streams."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from agent_nebula_platform.platform.errors import ConfigurationError

from .models import (
    A2UI_STABLE_VERSION,
    A2UI_SUPPORTED_VERSIONS,
    A2UIActionRequest,
    A2UISurface,
)

_FORBIDDEN_KEYS = frozenset(
    {
        "html",
        "rawHtml",
        "script",
        "javascript",
        "srcdoc",
        "dangerouslySetInnerHTML",
        "inlineScript",
    }
)
_REFERENCE_KEYS = frozenset({"child", "children"})


class A2UIProtocolPolicy:
    """Validate supported A2UI versions and optional catalog identifiers."""

    def __init__(
        self,
        *,
        supported_versions: Sequence[str] = A2UI_SUPPORTED_VERSIONS,
        preferred_version: str = A2UI_STABLE_VERSION,
        allowed_catalog_ids: Sequence[str] = (),
    ) -> None:
        versions = tuple(dict.fromkeys(str(value) for value in supported_versions))
        if not versions:
            raise ConfigurationError(
                "A2UI protocol policy requires a supported version"
            )
        if preferred_version not in versions:
            raise ConfigurationError(
                "A2UI preferred version must be included in supported versions"
            )
        self._versions = versions
        self._preferred = preferred_version
        self._catalog_ids = frozenset(str(value) for value in allowed_catalog_ids)

    @property
    def supported_versions(self) -> tuple[str, ...]:
        """Return versions accepted by this runtime in preference order."""

        return self._versions

    @property
    def preferred_version(self) -> str:
        """Return the version emitted by default by this runtime."""

        return self._preferred

    def validate_surface(self, surface: A2UISurface) -> str:
        """Require one supported version throughout the ordered surface stream."""

        versions = {message.version for message in surface.messages}
        if len(versions) != 1:
            raise ConfigurationError("A2UI surface messages must use one version")
        version = next(iter(versions))
        if version not in self._versions:
            raise ConfigurationError(
                f"A2UI message version is not supported by this runtime: {version}"
            )
        if self._catalog_ids:
            create = next(
                message
                for message in surface.messages
                if message.message_type == "createSurface"
            )
            payload = create.document["createSurface"]
            catalog_id = (
                payload.get("catalogId") if isinstance(payload, Mapping) else None
            )
            if catalog_id not in self._catalog_ids:
                raise ConfigurationError(
                    f"A2UI catalog is not approved by policy: {catalog_id}"
                )
        return version

    def validate_action(self, action: A2UIActionRequest) -> None:
        """Reject renderer actions using versions outside the runtime contract."""

        if action.version not in self._versions:
            raise ConfigurationError(
                f"A2UI action version is not supported by this runtime: {action.version}"
            )

    def negotiate(self, renderer_versions: Sequence[str]) -> str:
        """Choose the runtime-preferred version also supported by the renderer."""

        renderer = frozenset(str(value) for value in renderer_versions)
        for version in self._versions:
            if version in renderer:
                return version
        raise ConfigurationError("Renderer and runtime have no common A2UI version")


class A2UIComponentPolicy:
    """Validate A2UI components against a caller-approved component catalog."""

    def __init__(
        self,
        *,
        allowed_components: Sequence[str],
        allowed_functions: Sequence[str] = (),
    ) -> None:
        self._components = tuple(
            dict.fromkeys(str(value) for value in allowed_components)
        )
        self._functions = tuple(
            dict.fromkeys(str(value) for value in allowed_functions)
        )
        if not self._components:
            raise ConfigurationError(
                "A2UI component policy requires an approved catalog"
            )

    @property
    def allowed_components(self) -> tuple[str, ...]:
        """Return the exact component names approved for emitted surfaces."""

        return self._components

    @property
    def allowed_functions(self) -> tuple[str, ...]:
        """Return renderer-local functions explicitly approved by the host."""

        return self._functions

    def validate_surface(self, surface: A2UISurface) -> tuple[str, ...]:
        """Validate ordering, ownership, references, catalog, and executable fields."""

        created = False
        deleted = False
        component_ids: set[str] = set()
        references: set[str] = set()
        action_names: set[str] = set()

        for message in surface.messages:
            document = message.document
            self._reject_executable_content(document)
            payload = document[message.message_type]
            if not isinstance(payload, Mapping):
                raise ConfigurationError("A2UI message payload must be an object")
            message_surface = payload.get("surfaceId")
            if message_surface != surface.surface_id:
                raise ConfigurationError("A2UI message targets a different surface")

            if message.message_type == "createSurface":
                if created or deleted:
                    raise ConfigurationError("A2UI surface may be created only once")
                created = True
            elif not created:
                raise ConfigurationError("A2UI surface must be created before updates")

            if message.message_type == "deleteSurface":
                deleted = True
            elif deleted:
                raise ConfigurationError("A2UI messages cannot follow surface deletion")

            # A2UI v1.0 permits the initial component tree to be embedded in
            # createSurface.  Validate it through the same catalog/security
            # policy as subsequent updateComponents messages.
            if message.message_type in {"createSurface", "updateComponents"}:
                components = payload.get("components")
                if components is not None:
                    ids, refs, actions = self._validate_components(components)
                    component_ids.update(ids)
                    references.update(refs)
                    action_names.update(actions)
                elif message.message_type == "updateComponents":
                    raise ConfigurationError(
                        "A2UI updateComponents requires a component list"
                    )

        if not created:
            raise ConfigurationError("A2UI surface is missing createSurface")

        missing = sorted(references - component_ids)
        if missing:
            raise ConfigurationError(
                f"A2UI component references are unresolved: {missing}"
            )
        return tuple(sorted(action_names))

    def _validate_components(
        self,
        components: Any,
    ) -> tuple[set[str], set[str], set[str]]:
        if not isinstance(components, list):
            raise ConfigurationError("A2UI updateComponents requires a component list")
        seen: set[str] = set()
        references: set[str] = set()
        action_names: set[str] = set()
        for component in components:
            if not isinstance(component, Mapping):
                raise ConfigurationError("A2UI component definition must be an object")
            component_id = component.get("id")
            component_type = component.get("component")
            if not isinstance(component_id, str) or not component_id:
                raise ConfigurationError("A2UI component requires a stable id")
            if component_id in seen:
                raise ConfigurationError("A2UI component ids must be unique per update")
            seen.add(component_id)
            if (
                not isinstance(component_type, str)
                or component_type not in self._components
            ):
                raise ConfigurationError(
                    f"A2UI component is not approved by the renderer catalog: {component_type}"
                )
            references.update(self._component_references(component))
            action_names.update(self._validate_actions(component))
        return seen, references, action_names

    def _component_references(self, value: Any) -> set[str]:
        references: set[str] = set()
        if not isinstance(value, Mapping):
            return references
        for key, nested in value.items():
            if key not in _REFERENCE_KEYS:
                continue
            if isinstance(nested, str):
                references.add(nested)
            elif isinstance(nested, list):
                if not all(isinstance(item, str) and item for item in nested):
                    raise ConfigurationError(
                        f"A2UI component reference field '{key}' must contain ids"
                    )
                references.update(nested)
            else:
                raise ConfigurationError(
                    f"A2UI component reference field '{key}' has an invalid value"
                )
        return references

    def _validate_actions(self, value: Any) -> set[str]:
        action_names: set[str] = set()
        if isinstance(value, Mapping):
            action = value.get("action")
            if isinstance(action, Mapping):
                function_call = action.get("functionCall")
                if function_call is not None:
                    call = (
                        function_call.get("call")
                        if isinstance(function_call, Mapping)
                        else None
                    )
                    if call not in self._functions:
                        raise ConfigurationError(
                            f"A2UI renderer function is not approved by policy: {call}"
                        )
                # A2UI v1.0 represents user events as action.event.  Keep
                # functionCall validation independent because catalog-defined
                # renderer functions are not action events.
                event = action.get("event")
                if event is not None:
                    if not isinstance(event, Mapping):
                        raise ConfigurationError("A2UI action event must be an object")
                    action_name = event.get("name")
                    if not isinstance(action_name, str) or not action_name:
                        raise ConfigurationError("A2UI action name must be non-empty")
                    action_names.add(action_name)
            for nested in value.values():
                action_names.update(self._validate_actions(nested))
        elif isinstance(value, list):
            for nested in value:
                action_names.update(self._validate_actions(nested))
        return action_names

    def _reject_executable_content(self, value: Any) -> None:
        if isinstance(value, Mapping):
            invalid = _FORBIDDEN_KEYS.intersection(value)
            if invalid:
                raise ConfigurationError(
                    f"A2UI message contains prohibited executable content: {sorted(invalid)}"
                )
            for nested in value.values():
                self._reject_executable_content(nested)
        elif isinstance(value, list):
            for nested in value:
                self._reject_executable_content(nested)
