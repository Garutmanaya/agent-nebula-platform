"""Default exact-scope protected-resource policy."""

from __future__ import annotations

from agent_nebula_platform.platform.errors import AuthorizationError

from .models import AuthorizedRequestContext


class ExactScopeAuthorizationPolicy:
    """Require every method-specific opaque scope to be present in the token."""

    def authorize(
        self,
        *,
        context: AuthorizedRequestContext,
        required_scopes: tuple[str, ...],
    ) -> None:
        """Compare exact case-sensitive scope identifiers without normalization."""

        missing = sorted(set(required_scopes) - set(context.granted_scopes))
        if missing:
            raise AuthorizationError(
                "Access token does not grant the required protected-resource scopes",
                details={"missing_scopes": missing},
            )
