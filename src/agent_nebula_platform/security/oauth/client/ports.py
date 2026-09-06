"""Ports required by the OAuth client plugin."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from agent_nebula_sdk.oauth.rfc7523 import PrivateKeyJwtSigningKey
from agent_nebula_sdk.oauth.rfc9449 import DpopSigningKey

from .models import OAuthToken, OAuthTokenRequest


class OAuthClientIdentityProvider(Protocol):
    """Provide durable OAuth client identity and signing keys."""

    def client_id(self) -> str:
        """Return the protocol-facing OAuth client identifier."""

    def authentication_key(self) -> PrivateKeyJwtSigningKey:
        """Return the private-key JWT signing key."""

    def dpop_key(self) -> DpopSigningKey:
        """Return the DPoP signing key."""

    def dpop_key_thumbprint(self) -> str:
        """Return the RFC 7638 thumbprint for cache isolation."""


class OAuthTokenTransport(Protocol):
    """Send one prepared token request to the authorization server."""

    async def request_token(
        self,
        *,
        token_endpoint: str,
        form_fields: dict[str, str | tuple[str, ...]],
        dpop_proof: str,
    ) -> dict[str, object]:
        """Return the decoded OAuth token response."""


class OAuthTokenCache(Protocol):
    """Cache tokens by exact resource, scope set, and DPoP key identity."""

    def get(self, key: str, *, now: datetime) -> OAuthToken | None:
        """Return an unexpired cached token."""

    def put(self, key: str, token: OAuthToken) -> None:
        """Store one token without persisting reusable credentials implicitly."""

    def delete(self, key: str) -> None:
        """Remove one cached token."""


class OAuthTokenProvider(Protocol):
    """High-level token provider used by client integrations."""

    async def token(self, request: OAuthTokenRequest) -> OAuthToken:
        """Return a valid token for the exact request."""
