"""HTTPX transport for OAuth token requests."""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import httpx

from agent_nebula_platform.platform.errors import (
    AuthenticationError,
    RemoteServiceError,
)
from agent_nebula_platform.platform.execution_trace import (
    SECURITY_TRACE_HEADER,
    execution_headers,
    record_execution_event,
)


class HttpxOAuthTokenTransport:
    """Send OAuth token requests through a caller-owned verified HTTPX client."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def request_token(
        self,
        *,
        token_endpoint: str,
        form_fields: dict[str, str | tuple[str, ...]],
        dpop_proof: str,
    ) -> dict[str, object]:
        """Send one form-encoded request without logging security artifacts."""

        started = time.perf_counter()
        headers = {"DPoP": dpop_proof, **execution_headers()}
        try:
            response = await self._client.post(
                token_endpoint,
                data=form_fields,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise RemoteServiceError("OAuth token endpoint request failed") from exc
        duration_ms = max(0, round((time.perf_counter() - started) * 1000))
        encoded_trace = response.headers.get(SECURITY_TRACE_HEADER)
        if encoded_trace:
            try:
                padding = "=" * (-len(encoded_trace) % 4)
                decoded = base64.urlsafe_b64decode(encoded_trace + padding).decode(
                    "utf-8"
                )
                payload = json.loads(decoded)
                for step in (
                    payload.get("steps", ()) if isinstance(payload, dict) else ()
                ):
                    if isinstance(step, dict):
                        record_execution_event(step)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                pass
        record_execution_event(
            {
                "type": "OAUTH_TOKEN_HTTP",
                "source": "AGENT_RUNTIME",
                "status": "SUCCEEDED" if response.status_code < 400 else "FAILED",
                "duration_ms": duration_ms,
                "details": {
                    "token_endpoint": token_endpoint,
                    "http_status": response.status_code,
                },
            }
        )
        if response.status_code in {401, 403}:
            raise AuthenticationError("OAuth client authentication was rejected")
        if response.status_code >= 400:
            raise RemoteServiceError(
                "OAuth token endpoint rejected the request: "
                f"status={response.status_code} "
                f"body={response.text}"
            )
            # raise RemoteServiceError(
            #    f"OAuth token endpoint rejected the request: status={response.status_code}"
            # )
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise RemoteServiceError(
                "OAuth token endpoint returned invalid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise RemoteServiceError("OAuth token response must be an object")
        return payload
