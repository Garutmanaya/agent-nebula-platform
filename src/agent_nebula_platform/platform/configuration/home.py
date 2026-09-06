"""External Agent Runtime root and conventional path resolution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from agent_nebula_platform.platform.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class RuntimeHome:
    """Represent the normalized external root used by managed runtime assets."""

    root: Path

    @classmethod
    def resolve(
        cls,
        *,
        environment: Mapping[str, str],
        explicit_root: Path | None = None,
    ) -> RuntimeHome:
        """Resolve ``AGENT_RUNTIME_HOME`` or an explicit caller override.

        No working-directory fallback is used.  Managed mode must identify its
        external root explicitly so configuration, trust material, secrets,
        state, and logs cannot drift across process launch locations.
        """

        candidate = explicit_root
        if candidate is None:
            raw = environment.get("AGENT_RUNTIME_HOME")
            candidate = Path(raw) if raw else None
        if candidate is None:
            raise ConfigurationError(
                "AGENT_RUNTIME_HOME or an explicit runtime root is required"
            )
        return cls(candidate.expanduser().resolve())

    def config_file(self) -> Path:
        """Return the conventional standalone configuration file path."""

        return self.root / "config" / "application.conf"

    def secrets_directory(self) -> Path:
        """Return the conventional file-backed secret root."""

        return self.root / "secrets"
