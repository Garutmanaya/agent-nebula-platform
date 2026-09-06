"""Configuration and secret-provider ports for host-controlled integration."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

from agent_nebula_platform.platform.errors import ConfigurationError

T = TypeVar("T", bound=BaseModel)


class ConfigurationProvider(Protocol):
    """Resolve typed runtime settings from a caller-owned source."""

    def load(self, namespace: str, model_type: type[T]) -> T:
        """Return one validated settings model."""


class SecretProvider(Protocol):
    """Resolve secret text without exposing storage details to plugins."""

    def read_text(self, reference: str) -> str:
        """Return one secret value."""


class FileSecretProvider:
    """Read secrets from files rooted under an externally configured directory."""

    def __init__(self, root: Path) -> None:
        """Normalize the secret root once at the configuration boundary."""

        self._root = root.expanduser().resolve()

    def read_text(self, reference: str) -> str:
        """Read a non-empty secret file while preventing root escape."""

        if not reference or Path(reference).is_absolute():
            raise ConfigurationError("Secret reference must be a relative file path")
        path = (self._root / reference).resolve()
        if path != self._root and self._root not in path.parents:
            raise ConfigurationError("Secret path escapes configured root")
        if not path.is_file():
            raise ConfigurationError(
                "Secret file does not exist",
                details={"reference": reference},
            )
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            raise ConfigurationError(
                "Secret file is empty",
                details={"reference": reference},
            )
        return value
