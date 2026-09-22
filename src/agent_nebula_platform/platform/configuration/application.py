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
    console_logging: bool = True
    log_level: str = "INFO"
    metrics: bool = False
    telemetry: bool = False


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
            console_logging=self._boolean(section, "console_logging", default=True),
            log_level=self._log_level(section.get("log_level", "INFO")),
            metrics=self._boolean(section, "metrics", default=False),
            telemetry=self._boolean(section, "telemetry", default=False),
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

    @staticmethod
    def _boolean(section, field: str, *, default: bool) -> bool:
        """Read one optional boolean while reporting invalid values consistently."""

        try:
            return section.getboolean(field, fallback=default)
        except ValueError as exc:
            raise ConfigurationError(
                f"runtime.application.{field} must be true or false"
            ) from exc

    @staticmethod
    def _log_level(value: str) -> str:
        """Normalize and validate the standalone console log level."""

        level = value.strip().upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed:
            raise ConfigurationError(
                "runtime.application.log_level must be one of "
                "DEBUG, INFO, WARNING, ERROR, CRITICAL"
            )
        return level

