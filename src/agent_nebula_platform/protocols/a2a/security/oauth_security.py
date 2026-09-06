"""OAuth2 A2A authenticator backed by Runtime protected-resource security."""

from __future__ import annotations

from a2a.types import SecurityScheme

from agent_nebula_platform.platform.errors import AuthenticationError
from agent_nebula_platform.security.oauth.protected_resource import (
    ProtectedResourceRequest,
    ProtectedResourceService,
)

from .security import A2AAuthenticatedPrincipal, A2ASecurityRequest


class A2AOAuth2ProtectedResourceAuthenticator:
    """Validate OAuth2 access tokens with the existing SDK-backed resource server."""

    scheme_type = "oauth2_security_scheme"

    def __init__(self, service: ProtectedResourceService) -> None:
        self._service = service

    def authenticate(
        self,
        *,
        scheme_name: str,
        scheme: SecurityScheme,
        required_values: tuple[str, ...],
        request: A2ASecurityRequest,
    ) -> A2AAuthenticatedPrincipal:
        del scheme
        authorization = request.headers.get("authorization", "")
        expected_prefix = "DPoP " if self._service.dpop_required else "Bearer "
        if not authorization.startswith(expected_prefix):
            token_type = expected_prefix.strip()
            raise AuthenticationError(
                f"A2A OAuth2 request requires {token_type} authorization"
            )
        access_token = authorization[len(expected_prefix) :].strip()
        dpop_proof = request.headers.get("dpop", "").strip() or None
        if not access_token:
            raise AuthenticationError("A2A OAuth2 request is missing an access token")
        if self._service.dpop_required and not dpop_proof:
            raise AuthenticationError("A2A OAuth2 request is missing a DPoP proof")
        context = self._service.authenticate(
            ProtectedResourceRequest(
                access_token=access_token,
                dpop_proof=dpop_proof,
                http_method=request.http_method,
                target_uri=request.target_uri,
                required_scopes=required_values,
            )
        )
        return A2AAuthenticatedPrincipal(
            scheme_name=scheme_name,
            subject=context.subject,
            attributes={"client_id": context.client_id, "security": context},
        )
