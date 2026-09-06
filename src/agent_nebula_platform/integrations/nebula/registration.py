"""Optional Registry registration client for protocol-neutral agents."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from agent_nebula_platform.integrations.nebula.connector import RestNebulaConnector
from agent_nebula_platform.platform.tls import FileTlsContextProvider

from .configuration import NebulaConfiguration, NebulaRegistrationAuthentication


class NebulaRegistrationClient:
    """Register or resolve an agent through verified HTTPS Registry transport."""

    def __init__(self, configuration: NebulaConfiguration) -> None:
        self._configuration = configuration
        tls = configuration.tls
        context = FileTlsContextProvider(
            ca_file=tls.ca_file,
            certificate_file=tls.client_certificate_file,
            private_key_file=tls.client_private_key_file,
        ).create_client_context()
        headers: dict[str, str] = {}
        registration = configuration.registration
        if registration.authentication is NebulaRegistrationAuthentication.API_KEY:
            assert registration.api_key_file is not None
            api_key = registration.api_key_file.read_text(encoding="utf-8").strip()
            if not api_key:
                raise ValueError("Nebula registration API key file is empty")
            headers["X-API-Key"] = api_key
        self._client = httpx.AsyncClient(
            verify=context,
            timeout=httpx.Timeout(configuration.timeout_seconds),
            headers=headers,
        )
        self._connector = RestNebulaConnector(
            base_url=configuration.base_url, client=self._client
        )

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
        await self._client.aclose()
