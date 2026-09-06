"""Transport adapter for optional Agent Nebula enterprise DCR authentication.

AGENT NEBULA ADDITIONAL FUNCTIONALITY: RFC 7591 does not define ``X-API-Key``.
This adapter adds the header only for an Agent Nebula enterprise enrollment while delegating
all HTTP behavior to the SDK transport contract.
"""

from __future__ import annotations

from agent_nebula_sdk.ports.http import HttpResponse, HttpTransport


class EnterpriseRegistrationHttpTransport:
    """Decorate an SDK HTTP transport with an optional Agent Nebula API key."""

    def __init__(self, *, delegate: HttpTransport, api_key: str | None) -> None:
        """Store the delegate transport and optional enterprise registration credential."""

        self._delegate = delegate
        self._api_key = api_key

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> HttpResponse:
        """Delegate GET requests while applying the enterprise header when configured."""

        return self._delegate.get(url, headers=self._headers(headers))

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ) -> HttpResponse:
        """Delegate RFC 7591 POST requests with optional enterprise authentication."""

        return self._delegate.post(url, headers=self._headers(headers), body=body)

    def put(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ) -> HttpResponse:
        """Delegate PUT requests while applying the enterprise header when configured."""

        return self._delegate.put(url, headers=self._headers(headers), body=body)

    def delete(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        """Delegate DELETE requests while applying the enterprise header when configured."""

        return self._delegate.delete(url, headers=self._headers(headers))

    def _headers(self, headers: dict[str, str] | None) -> dict[str, str]:
        """Return a defensive header copy with the optional Agent Nebula API key."""

        merged = dict(headers or {})
        if self._api_key is not None:
            merged["X-API-Key"] = self._api_key
        return merged
