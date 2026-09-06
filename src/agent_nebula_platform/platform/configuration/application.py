"""Minimal application identity and filesystem-root configuration for Platform."""

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path

from agent_nebula_platform.platform.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class PlatformApplicationConfiguration:
    """Generic application identity shared by all protocol plugins."""

    name: str
    product_root: Path
    runtime_root: Path


class PlatformApplicationConfigurationLoader:
    """Load the generic ``runtime.application`` section from application.conf."""

    _SECTION = "runtime.application"

    def load(self, path: Path) -> PlatformApplicationConfiguration:
        """Read and validate application identity independently of any protocol."""

        parser = ConfigParser(interpolation=None)
        try:
            with path.open("r", encoding="utf-8") as stream:
                parser.read_file(stream)
        except (OSError, UnicodeError) as exc:
            raise ConfigurationError(
                f"Unable to read Platform application configuration: {path}"
            ) from exc
        if not parser.has_section(self._SECTION):
            raise ConfigurationError(f"application.conf must define [{self._SECTION}]")
        section = parser[self._SECTION]
        name = section.get("name", "").strip()
        if not name:
            raise ConfigurationError("runtime.application.name is required")
        return PlatformApplicationConfiguration(
            name=name,
            product_root=self._required_path(section.get("product_root"), path, "product_root"),
            runtime_root=self._required_path(section.get("runtime_root"), path, "runtime_root"),
        )

    @staticmethod
    def _required_path(value: str | None, config_path: Path, field: str) -> Path:
        """Resolve one required application path relative to application.conf."""

        if value is None or not value.strip():
            raise ConfigurationError(f"runtime.application.{field} is required")
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = config_path.parent / candidate
        return candidate.resolve()
