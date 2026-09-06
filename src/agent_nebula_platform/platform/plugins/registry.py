"""Deterministic plugin registration, status tracking, and duplicate protection."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from agent_nebula_platform.platform.errors import ConfigurationError

from .base import RuntimePlugin


class PluginStatus(StrEnum):
    """Runtime lifecycle state for one registered plugin."""

    AVAILABLE = "available"
    ENABLED = "enabled"
    INITIALIZED = "initialized"
    FAILED = "failed"
    NOT_IMPLEMENTED = "not_implemented"


class PluginRegistry:
    """Hold runtime plugins in deterministic initialization order."""

    def __init__(self, plugins: Iterable[RuntimePlugin] = ()) -> None:
        self._plugins: list[RuntimePlugin] = []
        self._status: dict[str, PluginStatus] = {}
        for plugin in plugins:
            self.register(plugin)

    def register(self, plugin: RuntimePlugin) -> None:
        """Register one enabled plugin and reject duplicate ownership."""

        if plugin.name in self._status:
            raise ConfigurationError(
                f"Runtime plugin is already registered: {plugin.name}"
            )
        self._plugins.append(plugin)
        self._status[plugin.name] = PluginStatus.ENABLED

    def mark_initialized(self, name: str) -> None:
        """Record successful plugin initialization."""

        self._require_registered(name)
        self._status[name] = PluginStatus.INITIALIZED

    def mark_failed(self, name: str) -> None:
        """Record plugin initialization or shutdown failure."""

        self._require_registered(name)
        self._status[name] = PluginStatus.FAILED

    def mark_enabled(self, name: str) -> None:
        """Return a closed plugin to its enabled composition state."""

        self._require_registered(name)
        self._status[name] = PluginStatus.ENABLED

    def status(self, name: str) -> PluginStatus:
        """Return the current lifecycle state for one plugin."""

        self._require_registered(name)
        return self._status[name]

    def snapshot(self) -> dict[str, PluginStatus]:
        """Return a defensive status snapshot for diagnostics."""

        return dict(self._status)

    @property
    def plugins(self) -> tuple[RuntimePlugin, ...]:
        """Return plugins in initialization order."""

        return tuple(self._plugins)

    def _require_registered(self, name: str) -> None:
        if name not in self._status:
            raise ConfigurationError(f"Runtime plugin is not registered: {name}")
