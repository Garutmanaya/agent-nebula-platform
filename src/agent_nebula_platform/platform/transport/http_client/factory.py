"""Verified HTTP client construction owned by Agent Runtime."""

from __future__ import annotations

import ssl
from collections.abc import Mapping
from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class RuntimeHttpClients:
    """Hold Runtime-managed outbound clients and close them deterministically."""

    nebula: httpx.AsyncClient
    provider: httpx.AsyncClient

    async def close(self) -> None:
        """Close every managed transport exactly once."""

        await self.provider.aclose()
        await self.nebula.aclose()


class RuntimeHttpClientFactory:
    """Create verified HTTPX clients from one Runtime TLS context."""

    def __init__(self, *, tls_context: ssl.SSLContext, timeout_seconds: float) -> None:
        """Store immutable transport policy used by all created clients."""

        self._tls_context = tls_context
        self._timeout = httpx.Timeout(timeout_seconds)

    def create(
        self, *, nebula_headers: Mapping[str, str] | None = None
    ) -> RuntimeHttpClients:
        """Create separate Nebula and provider clients with shared TLS policy."""

        return RuntimeHttpClients(
            nebula=httpx.AsyncClient(
                verify=self._tls_context,
                timeout=self._timeout,
                headers=dict(nebula_headers or {}),
            ),
            provider=httpx.AsyncClient(
                verify=self._tls_context,
                timeout=self._timeout,
            ),
        )
