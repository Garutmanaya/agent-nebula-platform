"""Pluggable non-authoritative runtime state stores."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Protocol


class RuntimeStateStore(Protocol):
    """Store recoverable local cache while Agent Nebula remains authoritative."""

    def read(self, key: str) -> dict[str, Any] | None:
        """Return a cached object or ``None`` when the key is absent."""
        ...

    def write(self, key: str, value: dict[str, Any]) -> None:
        """Persist one JSON-compatible object under the supplied key."""
        ...

    def delete(self, key: str) -> None:
        """Delete one cached value when present."""
        ...


class MemoryStateStore:
    """Process-local state for tests and ephemeral agents."""

    def __init__(self) -> None:
        self._values: dict[str, dict[str, Any]] = {}

    def read(self, key: str) -> dict[str, Any] | None:
        """Return a defensive copy of one cached object."""
        value = self._values.get(key)
        return dict(value) if value is not None else None

    def write(self, key: str, value: dict[str, Any]) -> None:
        """Cache a defensive copy of one object."""
        self._values[key] = dict(value)

    def delete(self, key: str) -> None:
        """Delete a cached object without failing when absent."""
        self._values.pop(key, None)


class JsonFileStateStore:
    """Atomic JSON cache rooted under a caller-selected runtime directory."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not key or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
            for c in key
        ):
            raise ValueError("Invalid runtime state key")
        return self._root / f"{key}.json"

    def read(self, key: str) -> dict[str, Any] | None:
        """Read and validate one JSON object from the runtime cache."""
        path = self._path(key)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("Runtime state document must be an object")
        return payload

    def write(self, key: str, value: dict[str, Any]) -> None:
        """Atomically replace one JSON cache document."""
        path = self._path(key)
        fd, temporary = tempfile.mkstemp(
            dir=self._root, prefix=f".{key}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def delete(self, key: str) -> None:
        """Delete one JSON cache document when present."""
        self._path(key).unlink(missing_ok=True)
