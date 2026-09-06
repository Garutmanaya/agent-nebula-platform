"""TOML loading for externally managed A2A server configuration.

The loader deliberately owns only file parsing and section extraction.  A2A
protocol construction is delegated to :mod:`agent_nebula_platform.protocols.a2a.server.configuration.factory`
so configuration I/O remains independent from protocol object creation.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from agent_nebula_platform.platform.errors import ConfigurationError


class A2AServerConfigurationLoader:
    """Load the A2A server Agent Card section from one external TOML file."""

    def load(self, path: Path) -> dict[str, Any]:
        """Read ``agent_card`` from ``path`` and return a defensive mapping copy."""

        configuration_path = path.expanduser().resolve()
        if not configuration_path.is_file():
            raise ConfigurationError(
                "A2A server configuration file does not exist",
                details={"path": str(configuration_path)},
            )
        try:
            with configuration_path.open("rb") as stream:
                document = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigurationError(
                "A2A server configuration file is invalid",
                details={"path": str(configuration_path)},
            ) from exc

        agent_card = document.get("agent_card")
        if not isinstance(agent_card, Mapping):
            raise ConfigurationError(
                "A2A server configuration must contain an [agent_card] section",
                details={"path": str(configuration_path)},
            )
        return deepcopy(dict(agent_card))
