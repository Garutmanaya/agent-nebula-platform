"""Tests for standards-driven OAuth Bearer versus DPoP A2A authentication."""

from types import SimpleNamespace

import pytest
from a2a.types import OAuth2SecurityScheme, OAuthFlows, SecurityScheme

from agent_nebula_platform.platform.errors import AuthenticationError
from agent_nebula_platform.protocols.a2a.security.oauth_security import (
    A2AOAuth2ProtectedResourceAuthenticator,
)
from agent_nebula_platform.protocols.a2a.security.security import A2ASecurityRequest


class _ProtectedResource:
    def __init__(self, *, dpop_required: bool) -> None:
        self.dpop_required = dpop_required
        self.last_request = None

    def authenticate(self, request):
        self.last_request = request
        return SimpleNamespace(subject="caller", client_id="client", granted_scopes=())


def _scheme():
    return SecurityScheme(
        oauth2_security_scheme=OAuth2SecurityScheme(flows=OAuthFlows())
    )


def _request(authorization: str, dpop: str | None = None):
    headers = {"authorization": authorization}
    if dpop:
        headers["dpop"] = dpop
    return A2ASecurityRequest(
        headers=headers, http_method="POST", target_uri="https://agent.example/a2a"
    )


def test_oauth_accepts_bearer_when_dpop_is_not_required():
    service = _ProtectedResource(dpop_required=False)
    authenticator = A2AOAuth2ProtectedResourceAuthenticator(service)
    principal = authenticator.authenticate(
        scheme_name="oauth",
        scheme=_scheme(),
        required_values=("read",),
        request=_request("Bearer token"),
    )
    assert principal.subject == "caller"
    assert service.last_request.dpop_proof is None


def test_oauth_requires_dpop_headers_when_resource_requires_dpop():
    service = _ProtectedResource(dpop_required=True)
    authenticator = A2AOAuth2ProtectedResourceAuthenticator(service)
    with pytest.raises(AuthenticationError, match="DPoP authorization"):
        authenticator.authenticate(
            scheme_name="oauth",
            scheme=_scheme(),
            required_values=(),
            request=_request("Bearer token"),
        )


def test_oauth_accepts_dpop_when_resource_requires_dpop():
    service = _ProtectedResource(dpop_required=True)
    authenticator = A2AOAuth2ProtectedResourceAuthenticator(service)
    authenticator.authenticate(
        scheme_name="oauth",
        scheme=_scheme(),
        required_values=(),
        request=_request("DPoP token", "proof"),
    )
    assert service.last_request.dpop_proof == "proof"
