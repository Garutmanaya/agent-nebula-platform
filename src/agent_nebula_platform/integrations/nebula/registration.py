"""Optional Registry registration client for protocol-neutral agents."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .configuration import NebulaConfiguration
from .transport import NebulaConnectorFactory


class NebulaRegistrationClient:
    """Register or resolve an agent through verified HTTPS Registry transport."""

    def __init__(self, configuration: NebulaConfiguration) -> None:
        self._configuration = configuration
        self._connector = NebulaConnectorFactory.create(configuration)

    async def register(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Resolve an existing registration first, otherwise create it."""
        settings = self._configuration.registration
        if settings.resolve_before_register:
            resolved = await self._connector.resolve_onboarding(payload)
            if resolved is not None:
                return resolved
        return await self._connector.onboard(payload)

    async def close(self) -> None:
        """Close the verified HTTPS client."""
        await self._connector.close()
