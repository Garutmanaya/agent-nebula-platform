"""Configuration-aware A2UI presentation composition tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_nebula_platform.a2ui import (
    A2UIComposer,
    A2UIConfiguration,
    A2UIPresentation,
)
from agent_nebula_platform.platform.errors import ConfigurationError

BASIC = "https://a2ui.org/specification/v1_0/catalogs/basic/catalog.json"
RICH = "https://agentnebula.ai/catalogs/a2ui/rich/v1/catalog.json"


def _configuration() -> A2UIConfiguration:
    """Return a two-catalog configuration with Basic as the surface default."""

    return A2UIConfiguration(
        enabled=True,
        version="v1.0",
        supported_catalog_ids=(BASIC, RICH),
        default_catalog_id=BASIC,
    )


def test_surface_uses_configured_version_and_default_catalog() -> None:
    """Provider code supplies composition while config supplies protocol identity."""

    surface = A2UIComposer(_configuration()).surface(
        surface_id="csv",
        components=[{"id": "root", "component": "Column", "children": []}],
        data_model={"csv_text": ""},
    )

    document = surface.messages[0].document
    assert document["version"] == "v1.0"
    assert document["createSurface"]["catalogId"] == BASIC
    assert document["createSurface"]["dataModel"] == {"csv_text": ""}


def test_update_data_model_does_not_rebuild_components() -> None:
    """Stable surfaces can update provider state without updateComponents."""

    surface = A2UIComposer(_configuration()).update(
        surface_id="csv",
        data_model={"summary_metrics": [{"label": "Rows", "value": 2}]},
    )

    assert len(surface.messages) == 1
    assert surface.messages[0].message_type == "updateDataModel"
    assert surface.messages[0].document["updateDataModel"]["path"] == "/"


def test_presentation_json_contains_ui_not_protocol_configuration(tmp_path: Path) -> None:
    """Presentation JSON loads components/data without catalog URLs or versions."""

    path = tmp_path / "presentation.json"
    path.write_text(
        json.dumps(
            {
                "components": [
                    {"id": "root", "component": "Column", "children": []}
                ],
                "dataModel": {"csv_text": ""},
            }
        ),
        encoding="utf-8",
    )

    presentation = A2UIPresentation.load(path)
    surface = A2UIComposer(_configuration()).surface_from_presentation(
        surface_id="csv",
        presentation=presentation,
    )

    assert presentation.data_model == {"csv_text": ""}
    assert surface.messages[0].document["createSurface"]["catalogId"] == BASIC


def test_multiple_catalogs_require_configured_default() -> None:
    """Composition fails closed instead of guessing between configured catalogs."""

    composer = A2UIComposer(
        A2UIConfiguration(
            enabled=True,
            supported_catalog_ids=(BASIC, RICH),
        )
    )

    with pytest.raises(ConfigurationError, match="default_catalog_id"):
        composer.surface(
            surface_id="main",
            components=[{"id": "root", "component": "Column"}],
        )
