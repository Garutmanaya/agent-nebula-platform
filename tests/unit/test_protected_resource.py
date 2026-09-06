"""Protected-resource authorization tests."""

from types import SimpleNamespace

import pytest

from agent_nebula_platform.platform.errors import AuthorizationError
from agent_nebula_platform.platform.events import NullEventSink
from agent_nebula_platform.security.oauth.protected_resource import (
    ExactScopeAuthorizationPolicy,
    ProtectedResourceRequest,
    ProtectedResourceService,
)


class Facade:
    """Return a trusted SDK-style security context."""

    def authenticate_request(self, **kwargs):
        return SimpleNamespace(
            subject="client-1",
            client_id="client-1",
            claims=SimpleNamespace(scope="airline.search airline.book"),
            dpop_proof=object(),
        )


def service() -> ProtectedResourceService:
    return ProtectedResourceService(
        expected_issuer="https://nebula.example",
        facade=Facade(),
        policy=ExactScopeAuthorizationPolicy(),
        events=NullEventSink(),
    )


def request(scope: str) -> ProtectedResourceRequest:
    return ProtectedResourceRequest(
        access_token="token",
        dpop_proof="proof",
        http_method="POST",
        target_uri="https://provider.example/a2a",
        required_scopes=(scope,),
    )


def test_exact_scope_is_authorized() -> None:
    """A granted provider-specific scope is accepted exactly."""

    context = service().authenticate(request("airline.search"))
    assert context.client_id == "client-1"


def test_scope_characters_are_not_normalized() -> None:
    """Colon and dot scope identifiers remain distinct opaque values."""

    with pytest.raises(AuthorizationError):
        service().authenticate(request("airline:search"))
