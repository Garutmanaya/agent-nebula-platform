"""Managed Agent Nebula discovery client for protocol callers.

This module keeps Registry transport, TLS, and authentication inside Platform so
higher-level facades can perform discovery without importing HTTPX or Registry
REST details.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .configuration import NebulaConfiguration
from .transport import NebulaConnectorFactory


class NebulaDiscoveryService:
    """Own verified Registry transport and expose only discovery operations."""

    def __init__(self, configuration: NebulaConfiguration) -> None:
        self._connector = NebulaConnectorFactory.create(configuration)
        self._closed = False

    async def search(self, parameters: Mapping[str, Any]) -> dict[str, Any]:
        """Search Agent Nebula using the Platform discovery contract."""
        if self._closed:
            raise RuntimeError("Nebula discovery service is closed")
        return await self._connector.discover(parameters)

    async def close(self) -> None:
        """Close the Platform-owned Registry HTTP client idempotently."""
        if self._closed:
            return
        self._closed = True
        await self._connector.close()


class NebulaDiscoveryServiceFactory:
    """Create managed discovery services from external ``nebula.conf`` files."""

    @staticmethod
    def create(path: Path) -> NebulaDiscoveryService:
        """Load and validate Registry configuration before opening transport."""
        return NebulaDiscoveryService(NebulaConfiguration.load(path))
