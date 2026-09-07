"""Transport-neutral Agent Nebula connector and REST implementation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol
from urllib.parse import urljoin

import httpx

from agent_nebula_platform.platform.errors import (
    AuthenticationError,
    RemoteServiceError,
)


class NebulaConnector(Protocol):
    """Operations needed by runtime plugins without exposing REST paths."""

    async def resolve_onboarding(
        self, payload: Mapping[str, Any]
    ) -> dict[str, Any] | None: ...
    async def onboard(self, payload: Mapping[str, Any]) -> dict[str, Any]: ...
    async def discover(self, parameters: Mapping[str, Any]) -> dict[str, Any]: ...
    async def deregister(
        self,
        *,
        external_agent_id: str,
        agent_id: str,
        agent_token: str,
        reason: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]: ...
    async def close(self) -> None: ...


class RestNebulaConnector:
    """HTTPX-based Agent Nebula connector with caller-owned or managed client."""

    def __init__(
        self,
        *,
        base_url: str,
        client: httpx.AsyncClient | None = None,
        onboarding_endpoint: str = "/api/v1/onboarding/registrations",
        resolution_endpoint: str = "/api/v1/onboarding/registrations/resolve",
        discovery_endpoint: str = "/api/v1/discovery/agents",
        lifecycle_prefix: str = "/api/v1/lifecycle/agents",
        owns_client: bool | None = None,
    ) -> None:
        self._base = base_url.rstrip("/") + "/"
        self._client = client or httpx.AsyncClient()
        self._owns = client is None if owns_client is None else owns_client
        self._onboarding = onboarding_endpoint
        self._resolution = resolution_endpoint
        self._discovery = discovery_endpoint
        self._lifecycle = lifecycle_prefix

    def _url(self, path: str) -> str:
        return urljoin(self._base, path.lstrip("/"))

    async def _json(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code in {401, 403}:
            raise AuthenticationError("Agent Nebula rejected runtime credentials")
        if response.status_code >= 400:
            raise RemoteServiceError(
                f"Agent Nebula request failed: status={response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise RemoteServiceError("Agent Nebula returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise RemoteServiceError("Agent Nebula response must be an object")
        return payload

    async def resolve_onboarding(self, payload):
        try:
            r = await self._client.post(self._url(self._resolution), json=dict(payload))
        except httpx.HTTPError as exc:
            raise RemoteServiceError(
                "Agent Nebula onboarding resolution failed"
            ) from exc
        if r.status_code == 404:
            return None
        return await self._json(r)

    async def onboard(self, payload):
        try:
            r = await self._client.post(self._url(self._onboarding), json=dict(payload))
        except httpx.HTTPError as exc:
            raise RemoteServiceError("Agent Nebula onboarding failed") from exc
        return await self._json(r)

    async def discover(self, parameters):
        try:
            r = await self._client.get(
                self._url(self._discovery), params=dict(parameters)
            )
        except httpx.HTTPError as exc:
            raise RemoteServiceError("Agent Nebula discovery failed") from exc
        return await self._json(r)

    async def deregister(
        self, *, external_agent_id, agent_id, agent_token, reason, correlation_id=None
    ):
        headers = {"X-Agent-Id": agent_id, "X-Agent-Token": agent_token}
        body = {"reason": reason}
        if correlation_id is not None:
            body["correlation_id"] = correlation_id
        try:
            r = await self._client.post(
                self._url(f"{self._lifecycle}/{external_agent_id}/deregister"),
                json=body,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise RemoteServiceError("Agent Nebula lifecycle request failed") from exc
        return await self._json(r)

    async def close(self) -> None:
        if self._owns:
            await self._client.aclose()


class DisabledNebulaConnector:
    """Fail-closed connector used when optional Agent Nebula integration is absent."""

    @staticmethod
    def _disabled() -> None:
        raise RemoteServiceError("Agent Nebula integration is not configured")

    async def resolve_onboarding(self, payload):
        self._disabled()

    async def onboard(self, payload):
        self._disabled()

    async def discover(self, parameters):
        self._disabled()

    async def deregister(self, **kwargs):
        self._disabled()

    async def close(self) -> None:
        return None
