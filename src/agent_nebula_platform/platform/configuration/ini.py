"""Optional INI configuration adapter for new or standalone agents."""

from __future__ import annotations

from configparser import ConfigParser
from configparser import Error as ConfigParserError
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from agent_nebula_platform.platform.errors import ConfigurationError

T = TypeVar("T", bound=BaseModel)


class IniConfigurationProvider:
    """Load strict Pydantic settings without requiring hosts to adopt INI."""

    def __init__(self, path: Path) -> None:
        """Read one explicit configuration file without interpolation."""

        if not path.is_file():
            raise ConfigurationError(f"Configuration file does not exist: {path}")
        self._parser = ConfigParser(interpolation=None)
        try:
            loaded = self._parser.read(path)
        except ConfigParserError as exc:
            raise ConfigurationError(f"Configuration file is invalid: {path}") from exc
        if not loaded:
            raise ConfigurationError(f"Configuration file could not be read: {path}")

    def load(self, namespace: str, model_type: type[T]) -> T:
        """Validate one INI section against the supplied model."""

        if not self._parser.has_section(namespace):
            raise ConfigurationError(f"Missing configuration section: {namespace}")
        try:
            return model_type.model_validate(dict(self._parser.items(namespace)))
        except ValidationError as exc:
            raise ConfigurationError(
                f"Invalid configuration section: {namespace}"
            ) from exc

    def as_nested_mapping(self, *, section_prefix: str = "") -> dict[str, Any]:
        """Return INI sections as a nested mapping for layered model loading.

        With ``section_prefix='runtime.'``, the section ``runtime.server`` maps
        to ``{"server": {...}}``.  Sections outside the requested namespace
        are ignored so host applications may keep unrelated settings in the
        same file without exposing them to Agent Runtime.
        """

        result: dict[str, Any] = {}
        for section in self._parser.sections():
            if section_prefix and not section.startswith(section_prefix):
                continue
            relative = section[len(section_prefix) :] if section_prefix else section
            parts = tuple(part for part in relative.split(".") if part)
            if not parts:
                continue
            current = result
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current[parts[-1]] = dict(self._parser.items(section))
        return result
