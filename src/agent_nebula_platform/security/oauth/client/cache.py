"""In-memory OAuth token cache implementation."""

from __future__ import annotations

from datetime import datetime

from .models import OAuthToken


class MemoryOAuthTokenCache:
    """Keep non-persistent token state for one runtime process."""

    def __init__(self) -> None:
        self._tokens: dict[str, OAuthToken] = {}

    def get(self, key: str, *, now: datetime) -> OAuthToken | None:
        """Return an unexpired token and evict expired entries."""

        token = self._tokens.get(key)
        if token is None:
            return None
        if token.expires_at <= now:
            self._tokens.pop(key, None)
            return None
        return token

    def put(self, key: str, token: OAuthToken) -> None:
        """Store one token in process memory."""

        self._tokens[key] = token

    def delete(self, key: str) -> None:
        """Remove one token from memory."""

        self._tokens.pop(key, None)
