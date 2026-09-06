"""Storage ports and implementations for A2UI sessions."""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
from pathlib import Path
from typing import Protocol

from .models import A2UISessionSnapshot


class A2UISessionStore(Protocol):
    """Persist immutable A2UI session snapshots."""

    async def create(
        self,
        session: A2UISessionSnapshot,
    ) -> A2UISessionSnapshot:
        """Create one new session and reject identifier reuse."""

    async def get(self, session_id: str) -> A2UISessionSnapshot:
        """Return one session or fail when it does not exist."""

    async def save(
        self,
        session: A2UISessionSnapshot,
    ) -> A2UISessionSnapshot:
        """Replace one existing session snapshot."""

    async def delete(self, session_id: str) -> None:
        """Delete one session if present."""


class MemoryA2UISessionStore:
    """Process-local session store for tests and ephemeral runtimes."""

    def __init__(self) -> None:
        """Initialize an empty async-safe registry."""

        self._items: dict[str, A2UISessionSnapshot] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        session: A2UISessionSnapshot,
    ) -> A2UISessionSnapshot:
        """Create one session while preventing identifier reuse."""

        async with self._lock:
            if session.session_id in self._items:
                raise ValueError("A2UI session already exists")
            self._items[session.session_id] = session
            return session

    async def get(self, session_id: str) -> A2UISessionSnapshot:
        """Return one stored session snapshot."""

        async with self._lock:
            try:
                return self._items[session_id]
            except KeyError as exc:
                raise KeyError("A2UI session was not found") from exc

    async def save(
        self,
        session: A2UISessionSnapshot,
    ) -> A2UISessionSnapshot:
        """Replace one existing session snapshot."""

        async with self._lock:
            if session.session_id not in self._items:
                raise KeyError("A2UI session was not found")
            self._items[session.session_id] = session
            return session

    async def delete(self, session_id: str) -> None:
        """Remove one session without failing repeated cleanup."""

        async with self._lock:
            self._items.pop(session_id, None)


class JsonFileA2UISessionStore:
    """Atomic JSON persistence for standalone Runtime deployments."""

    _SAFE_SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")

    def __init__(self, directory: Path) -> None:
        """Create the contained session directory if necessary."""

        self._directory = Path(directory).expanduser().resolve()
        self._directory.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def create(
        self,
        session: A2UISessionSnapshot,
    ) -> A2UISessionSnapshot:
        """Atomically create one session document."""

        async with self._lock:
            path = self._path(session.session_id)
            if path.exists():
                raise ValueError("A2UI session already exists")
            self._write(path, session)
            return session

    async def get(self, session_id: str) -> A2UISessionSnapshot:
        """Load and validate one persisted session document."""

        async with self._lock:
            path = self._path(session_id)
            if not path.is_file():
                raise KeyError("A2UI session was not found")
            return A2UISessionSnapshot.model_validate_json(
                path.read_text(encoding="utf-8")
            )

    async def save(
        self,
        session: A2UISessionSnapshot,
    ) -> A2UISessionSnapshot:
        """Atomically replace one existing session document."""

        async with self._lock:
            path = self._path(session.session_id)
            if not path.is_file():
                raise KeyError("A2UI session was not found")
            self._write(path, session)
            return session

    async def delete(self, session_id: str) -> None:
        """Delete one persisted session if present."""

        async with self._lock:
            self._path(session_id).unlink(missing_ok=True)

    def _path(self, session_id: str) -> Path:
        """Return a contained path for one opaque safe session identifier."""

        if not self._SAFE_SESSION_ID.fullmatch(session_id):
            raise ValueError("A2UI session identifier has an invalid format")
        candidate = (self._directory / f"{session_id}.json").resolve()
        if self._directory not in candidate.parents:
            raise ValueError("A2UI session path escapes the configured directory")
        return candidate

    @staticmethod
    def _write(path: Path, session: A2UISessionSnapshot) -> None:
        """Write one session atomically with private temporary-file mode."""

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=path.parent,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(session.model_dump_json(indent=2))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
