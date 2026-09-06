"""Managed Agent Nebula discovery client for protocol callers.

This module keeps Registry transport, TLS, and authentication inside Platform so
higher-level facades can perform discovery without importing HTTPX or Registry
REST details.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

from agent_nebula_platform.platform.tls import FileTlsContextProvider

from .configuration import NebulaConfiguration, NebulaRegistrationAuthentication
from .connector import RestNebulaConnector


class NebulaDiscoveryService:
    """Own verified Registry transport and expose only discovery operations."""

    def __init__(self, configuration: NebulaConfiguration) -> None:
        tls = configuration.tls
        tls_context = FileTlsContextProvider(
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
                raise ValueError("Nebula API key file is empty")
            headers["X-API-Key"] = api_key
        self._client = httpx.AsyncClient(
            verify=tls_context,
            timeout=httpx.Timeout(configuration.timeout_seconds),
            headers=headers,
        )
        self._connector = RestNebulaConnector(
            base_url=configuration.base_url, client=self._client
        )
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
        await self._client.aclose()


class NebulaDiscoveryServiceFactory:
    """Create managed discovery services from external ``nebula.conf`` files."""

    @staticmethod
    def create(path: Path) -> NebulaDiscoveryService:
        """Load and validate Registry configuration before opening transport."""
        return NebulaDiscoveryService(NebulaConfiguration.load(path))
