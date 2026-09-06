"""Shared preset resources and lifecycle helpers.

Presets may create infrastructure objects such as HTTP clients. This module
keeps ownership explicit so embedded applications never lose control of their
own resources and standalone compositions can close only what they created.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.plugins.base import RuntimePlugin

AsyncCloser = Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ManagedResource:
    """Describe one preset-owned asynchronous resource.

    The name is used only for diagnostics. The closer is invoked during
    reverse-order runtime shutdown and must not expose secret material in
    raised messages.
    """

    name: str
    close: AsyncCloser


class ManagedResourcesPlugin(RuntimePlugin):
    """Close resources created by a preset after all dependent plugins stop.

    This plugin is intentionally placed first in a preset's plugin sequence.
    Agent Runtime closes plugins in reverse order, which guarantees transports
    and business capabilities release their references before shared clients
    and connectors are closed.
    """

    def __init__(self, resources: Iterable[ManagedResource]) -> None:
        self._resources = tuple(resources)

    @property
    def name(self) -> str:
        """Return the stable plugin identifier."""

        return "preset.managed_resources"

    async def initialize(self, context: RuntimeContext) -> None:
        """Register a marker without altering caller-owned resources."""

        context.services.register(self.name, self)

    async def close(self, context: RuntimeContext) -> None:
        """Close preset-owned resources in reverse construction order."""

        failures: list[Exception] = []
        for resource in reversed(self._resources):
            try:
                await resource.close()
            except Exception as exc:  # noqa: BLE001  # pragma: no cover - defensive aggregation
                failures.append(exc)
        context.services.remove(self.name)
        if failures:
            raise RuntimeError(
                "One or more preset-managed resources failed to close"
            ) from failures[0]
