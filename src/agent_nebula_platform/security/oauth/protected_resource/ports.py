"""Ports for provider-local protected-resource authorization."""

from __future__ import annotations

from typing import Protocol

from .models import AuthorizedRequestContext


class ProtectedResourceAuthorizationPolicy(Protocol):
    """Apply provider-owned authorization after token and DPoP authentication."""

    def authorize(
        self,
        *,
        context: AuthorizedRequestContext,
        required_scopes: tuple[str, ...],
    ) -> None:
        """Raise when the authenticated caller lacks provider-local authority."""
