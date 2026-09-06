"""Layered typed configuration loading for managed Agent Runtime deployments."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from agent_nebula_platform.platform.errors import ConfigurationError

from .ini import IniConfigurationProvider
from .sources import cli_overrides, environment_overrides, merge_mappings

T = TypeVar("T", bound=BaseModel)


class LayeredSettingsLoader:
    """Load one typed model using the documented configuration precedence."""

    def __init__(self, *, environment_prefix: str = "AGENT_RUNTIME__") -> None:
        """Create a loader with an explicit environment-variable namespace."""

        self._environment_prefix = environment_prefix

    def load(
        self,
        model_type: type[T],
        *,
        defaults: Mapping[str, Any],
        config_file: Path | None,
        environment: Mapping[str, str],
        command_line: Mapping[str, Any] | Sequence[str] | None = None,
    ) -> T:
        """Load defaults, file, environment, and CLI layers in that order."""

        file_values: Mapping[str, Any] = {}
        if config_file is not None:
            file_values = IniConfigurationProvider(config_file).as_nested_mapping(
                section_prefix="runtime."
            )
        effective = merge_mappings(
            defaults,
            file_values,
            environment_overrides(
                environment,
                prefix=self._environment_prefix,
            ),
            cli_overrides(command_line),
        )
        try:
            return model_type.model_validate(effective)
        except ValidationError as exc:
            raise ConfigurationError(
                "Effective Agent Runtime configuration is invalid",
                details={"errors": exc.errors(include_url=False)},
            ) from exc
