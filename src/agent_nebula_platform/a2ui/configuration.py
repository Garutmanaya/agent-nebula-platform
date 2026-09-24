"""Independent configuration for the A2UI protocol subsystem.

A2UI configuration is intentionally loaded from its own ``a2ui.conf`` file.
A2A server/client configuration must not own or parse A2UI protocol settings.
"""

from __future__ import annotations

import configparser
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent_nebula_platform.a2ui.models import (
    A2UI_STABLE_VERSION,
    A2UI_SUPPORTED_VERSIONS,
)
from agent_nebula_platform.platform.errors import ConfigurationError


class A2UIConfiguration(BaseModel):
    """Configuration owned by the transport-independent A2UI subsystem."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    version: str = A2UI_STABLE_VERSION
    supported_catalog_ids: tuple[str, ...] = ()
    default_catalog_id: str | None = None
    accepts_inline_catalogs: bool = False

    @model_validator(mode="after")
    def validate_version(self) -> A2UIConfiguration:
        """Reject protocol versions that this Platform build cannot process."""

        if self.version not in A2UI_SUPPORTED_VERSIONS:
            raise ValueError(
                f"Unsupported A2UI version {self.version!r}; "
                f"supported versions: {', '.join(A2UI_SUPPORTED_VERSIONS)}"
            )
        if self.default_catalog_id is not None:
            if not self.default_catalog_id.strip():
                raise ValueError("A2UI default catalog id must not be empty")
            if self.default_catalog_id not in self.supported_catalog_ids:
                raise ValueError(
                    "A2UI default catalog id must be included in supported catalog ids"
                )
        return self

    @classmethod
    def load(cls, path: Path) -> A2UIConfiguration:
        """Load one explicit ``a2ui.conf`` file and no A2A configuration."""

        config_path = path.expanduser().resolve()
        parser = configparser.ConfigParser(interpolation=None)
        try:
            with config_path.open(encoding="utf-8") as stream:
                parser.read_file(stream)
        except (OSError, configparser.Error) as exc:
            raise ConfigurationError(
                "A2UI configuration file is invalid",
                details={"path": str(config_path)},
            ) from exc

        if not parser.has_section("a2ui"):
            raise ConfigurationError("a2ui.conf requires an [a2ui] section")

        section = parser["a2ui"]
        known = {
            "enabled",
            "version",
            "supported_catalog_ids",
            "default_catalog_id",
            "accepts_inline_catalogs",
        }
        unknown = set(section) - known
        if unknown:
            raise ConfigurationError(
                "a2ui.conf contains unsupported settings",
                details={"settings": sorted(unknown)},
            )

        try:
            enabled = section.getboolean("enabled", fallback=False)
            accepts_inline_catalogs = section.getboolean(
                "accepts_inline_catalogs", fallback=False
            )
        except ValueError as exc:
            raise ConfigurationError("a2ui.conf contains an invalid boolean") from exc

        catalogs = tuple(
            value.strip()
            for value in section.get("supported_catalog_ids", fallback="").split(",")
            if value.strip()
        )
        try:
            return cls(
                enabled=enabled,
                version=section.get("version", fallback=A2UI_STABLE_VERSION).strip(),
                supported_catalog_ids=catalogs,
                default_catalog_id=(
                    section.get("default_catalog_id", fallback="").strip() or None
                ),
                accepts_inline_catalogs=accepts_inline_catalogs,
            )
        except ValueError as exc:
            raise ConfigurationError(
                "A2UI configuration is invalid",
                details={"path": str(config_path)},
            ) from exc
