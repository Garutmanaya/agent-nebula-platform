from pathlib import Path

import pytest

from agent_nebula_platform.a2ui.configuration import A2UIConfiguration
from agent_nebula_platform.platform.errors import ConfigurationError


def test_loads_independent_a2ui_configuration(tmp_path: Path) -> None:
    path = tmp_path / "a2ui.conf"
    path.write_text(
        """[a2ui]\nenabled = true\nversion = v1.0\nsupported_catalog_ids = catalog-a, catalog-b\naccepts_inline_catalogs = true\n""",
        encoding="utf-8",
    )

    config = A2UIConfiguration.load(path)

    assert config.enabled is True
    assert config.version == "v1.0"
    assert config.supported_catalog_ids == ("catalog-a", "catalog-b")
    assert config.accepts_inline_catalogs is True


def test_rejects_non_a2ui_configuration(tmp_path: Path) -> None:
    path = tmp_path / "a2aserver.conf"
    path.write_text("[server]\nhost = 127.0.0.1\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match=r"requires an \[a2ui\] section"):
        A2UIConfiguration.load(path)


def test_rejects_unsupported_a2ui_version(tmp_path: Path) -> None:
    path = tmp_path / "a2ui.conf"
    path.write_text("[a2ui]\nversion = v0.9.1\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="A2UI configuration is invalid"):
        A2UIConfiguration.load(path)
