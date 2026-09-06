"""Runtime-owned OAuth/DPoP protected HTTP invocation capability."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import httpx

from agent_nebula_platform.platform.errors import RemoteServiceError
from agent_nebula_platform.platform.execution_trace import (
    execution_headers,
    record_execution_event,
)

from .service import OAuthClientService


class ProtectedHttpClient:
    """Send verified JSON requests with Runtime-managed OAuth and DPoP headers."""

    def __init__(self, *, client: httpx.AsyncClient, oauth: OAuthClientService) -> None:
        self._client = client
        self._oauth = oauth

    async def post_json(
        self,
        *,
        url: str,
        resource: str,
        scopes: tuple[str, ...],
        body: Mapping[str, Any],
    ) -> dict[str, Any]:
        """POST one resource-specific DPoP-protected JSON request.

        The trace exposes the logical A2A request/response as separate events.
        Authorization and DPoP headers are intentionally omitted; Runtime's
        execution-trace boundary redacts them even if a future transport adds
        those fields accidentally.
        """

        protected = await self._oauth.protected_request(
            http_method="POST",
            target_uri=url,
            resource=resource,
            scopes=scopes,
        )
        outbound_headers = dict(protected.headers)
        outbound_headers.update(execution_headers())

        record_execution_event(
            {
                "type": "A2A_REQUEST",
                "source": "ORCHESTRATOR",
                "component": "A2A",
                "direction": "REQUEST",
                "target": url,
                "status": "STARTED",
                "duration_ms": 0,
                "request": {
                    "method": "POST",
                    "resource": resource,
                    "scopes": list(scopes),
                    "body": dict(body),
                    "dpop_protected": True,
                },
                "details": {"endpoint": url},
            }
        )
        started = time.perf_counter()
        try:
            response = await self._client.post(
                url,
                headers=outbound_headers,
                json=dict(body),
            )
        except httpx.HTTPError as exc:
            record_execution_event(
                {
                    "type": "A2A_RESPONSE",
                    "source": "PROVIDER_AGENT",
                    "component": "A2A",
                    "direction": "RESPONSE",
                    "target": "ORCHESTRATOR",
                    "status": "FAILED",
                    "duration_ms": _duration_ms(started),
                    "response": {"error_type": type(exc).__name__},
                    "details": {"endpoint": url, "resource": resource},
                }
            )
            raise RemoteServiceError("Protected HTTP request failed") from exc

        if response.status_code >= 400:
            record_execution_event(
                {
                    "type": "A2A_RESPONSE",
                    "source": "PROVIDER_AGENT",
                    "component": "A2A",
                    "direction": "RESPONSE",
                    "target": "ORCHESTRATOR",
                    "status": "FAILED",
                    "duration_ms": _duration_ms(started),
                    "response": {
                        "http_status": response.status_code,
                        "content_type": response.headers.get("content-type", ""),
                    },
                    "details": {"endpoint": url, "resource": resource},
                }
            )
            raise RemoteServiceError(
                f"Protected HTTP request was rejected: status={response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            record_execution_event(
                {
                    "type": "A2A_RESPONSE",
                    "source": "PROVIDER_AGENT",
                    "component": "A2A",
                    "direction": "RESPONSE",
                    "target": "ORCHESTRATOR",
                    "status": "FAILED",
                    "duration_ms": _duration_ms(started),
                    "response": {
                        "http_status": response.status_code,
                        "content_type": response.headers.get("content-type", ""),
                        "validation": "invalid_json",
                    },
                    "details": {"endpoint": url, "resource": resource},
                }
            )
            raise RemoteServiceError(
                "Protected HTTP response was not valid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise RemoteServiceError("Protected HTTP response must be a JSON object")

        record_execution_event(
            {
                "type": "A2A_RESPONSE",
                "source": "PROVIDER_AGENT",
                "component": "A2A",
                "direction": "RESPONSE",
                "target": "ORCHESTRATOR",
                "status": "SUCCEEDED",
                "duration_ms": _duration_ms(started),
                "response": {
                    "http_status": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "body": payload,
                    "validation": "json_object",
                },
                "details": {"endpoint": url, "resource": resource},
            }
        )
        return payload


def _duration_ms(started: float) -> int:
    """Return elapsed milliseconds for one protected HTTP exchange."""

    return max(0, round((time.perf_counter() - started) * 1000))
