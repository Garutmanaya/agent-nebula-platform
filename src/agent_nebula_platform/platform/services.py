"""Runtime-local service registry for plugin collaboration."""

from __future__ import annotations

from typing import TypeVar, cast

from agent_nebula_platform.platform.errors import ConfigurationError

T = TypeVar("T")


class RuntimeServiceRegistry:
    """Store initialized plugin services without becoming a global locator."""

    def __init__(self) -> None:
        self._services: dict[str, object] = {}

    def register(self, name: str, service: object) -> None:
        """Register one service and reject duplicate ownership."""

        if name in self._services:
            raise ConfigurationError(f"Runtime service is already registered: {name}")
        self._services[name] = service

    def remove(self, name: str) -> None:
        """Remove one service during reverse plugin shutdown."""

        self._services.pop(name, None)

    def require(self, name: str, expected_type: type[T]) -> T:
        """Return one initialized service with a defensive runtime type check."""

        service = self._services.get(name)
        if service is None:
            raise ConfigurationError(f"Runtime service is not initialized: {name}")
        if not isinstance(service, expected_type):
            raise ConfigurationError(f"Runtime service has unexpected type: {name}")
        return cast(T, service)

    def names(self) -> tuple[str, ...]:
        """Return initialized service names for diagnostics."""

        return tuple(self._services)
