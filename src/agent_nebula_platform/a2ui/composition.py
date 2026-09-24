"""Configuration-aware composition helpers for provider-owned A2UI surfaces.

Application code owns declarative component composition and data.  This module
owns protocol envelope construction so providers do not duplicate A2UI version,
catalog, create-surface, or incremental-update mechanics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_nebula_platform.platform.errors import ConfigurationError

from .configuration import A2UIConfiguration
from .models import A2UIMessage, A2UISurface


class A2UIPresentation(BaseModel):
    """Declarative provider presentation loaded independently of A2UI protocol config."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    components: tuple[dict[str, Any], ...] = Field(min_length=1)
    data_model: dict[str, Any] = Field(default_factory=dict, alias="dataModel")

    @classmethod
    def load(cls, path: Path) -> "A2UIPresentation":
        """Load one JSON presentation containing components and initial data only."""

        presentation_path = path.expanduser().resolve()
        try:
            document = json.loads(presentation_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(
                "A2UI presentation JSON is invalid",
                details={"path": str(presentation_path)},
            ) from exc
        try:
            return cls.model_validate(document)
        except ValueError as exc:
            raise ConfigurationError(
                "A2UI presentation is invalid",
                details={"path": str(presentation_path)},
            ) from exc


class A2UIComposer:
    """Compose A2UI v1.0 surface streams from authoritative A2UI configuration."""

    def __init__(self, configuration: A2UIConfiguration) -> None:
        """Bind one immutable A2UI configuration to all emitted surfaces."""

        if not configuration.enabled:
            raise ConfigurationError("A2UI composition requires A2UI to be enabled")
        self._configuration = configuration

    def surface(
        self,
        *,
        surface_id: str,
        components: tuple[dict[str, Any], ...] | list[dict[str, Any]],
        data_model: dict[str, Any] | None = None,
        catalog_id: str | None = None,
    ) -> A2UISurface:
        """Create a new surface using configured version and catalog policy."""

        selected_catalog = self._resolve_catalog(catalog_id)
        return A2UISurface(
            surface_id=surface_id,
            messages=(
                A2UIMessage(
                    document={
                        "version": self._configuration.version,
                        "createSurface": {
                            "surfaceId": surface_id,
                            "catalogId": selected_catalog,
                            "components": [dict(component) for component in components],
                            "dataModel": dict(data_model or {}),
                        },
                    }
                ),
            ),
        )

    def surface_from_presentation(
        self,
        *,
        surface_id: str,
        presentation: A2UIPresentation,
        data_model: dict[str, Any] | None = None,
        catalog_id: str | None = None,
    ) -> A2UISurface:
        """Create a surface from a loaded presentation with optional runtime data."""

        model = dict(presentation.data_model)
        if data_model is not None:
            model.update(data_model)
        return self.surface(
            surface_id=surface_id,
            components=presentation.components,
            data_model=model,
            catalog_id=catalog_id,
        )

    def update(
        self,
        *,
        surface_id: str,
        data_model: dict[str, Any] | None = None,
        components: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None = None,
        path: str = "/",
    ) -> A2UISurface:
        """Compose incremental data and/or component updates for an existing surface."""

        if data_model is None and components is None:
            raise ValueError("A2UI update requires data_model and/or components")
        messages: list[A2UIMessage] = []
        if data_model is not None:
            messages.append(
                A2UIMessage(
                    document={
                        "version": self._configuration.version,
                        "updateDataModel": {
                            "surfaceId": surface_id,
                            "path": path,
                            "value": dict(data_model),
                        },
                    }
                )
            )
        if components is not None:
            messages.append(
                A2UIMessage(
                    document={
                        "version": self._configuration.version,
                        "updateComponents": {
                            "surfaceId": surface_id,
                            "components": [dict(component) for component in components],
                        },
                    }
                )
            )
        return A2UISurface(surface_id=surface_id, messages=tuple(messages))

    def _resolve_catalog(self, requested: str | None) -> str:
        """Resolve a surface catalog without introducing a second source of truth."""

        supported = self._configuration.supported_catalog_ids
        selected = requested or self._configuration.default_catalog_id
        if selected is None and len(supported) == 1:
            selected = supported[0]
        if selected is None:
            raise ConfigurationError(
                "A2UI surface catalog is ambiguous; configure default_catalog_id"
            )
        if supported and selected not in supported:
            raise ConfigurationError(
                f"A2UI catalog is not configured for this runtime: {selected}"
            )
        return selected
