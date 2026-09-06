"""OAuth client orchestration tests."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from agent_nebula_platform.platform.events import NullEventSink
from agent_nebula_platform.security.oauth.client import (
    MemoryOAuthTokenCache,
    OAuthClientService,
    OAuthTokenRequest,
)


class Identity:
    """Test identity provider returning opaque keys to the mocked facade."""

    def client_id(self) -> str:
        return "client-1"

    def authentication_key(self):
        return object()

    def dpop_key(self):
        return object()

    def dpop_key_thumbprint(self) -> str:
        return "thumbprint-1"


class Facade:
    """Record SDK facade composition calls."""

    def __init__(self) -> None:
        self.token_calls = 0

    def build_token_request(self, **kwargs):
        self.token_calls += 1
        return SimpleNamespace(
            form_fields={"grant_type": "client_credentials"},
            dpop_proof=SimpleNamespace(proof="proof"),
        )

    def build_protected_request(self, **kwargs):
        return SimpleNamespace(headers={"Authorization": "DPoP token", "DPoP": "proof"})


class Transport:
    """Return a deterministic successful token response."""

    def __init__(self) -> None:
        self.calls = 0

    async def request_token(self, **kwargs):
        self.calls += 1
        return {
            "access_token": "token",
            "token_type": "DPoP",
            "expires_in": 120,
            "scope": "airline.search",
        }


@pytest.mark.asyncio
async def test_token_cache_isolated_by_exact_resource_and_scope() -> None:
    """Exact opaque scope strings participate in the cache key unchanged."""

    facade = Facade()
    transport = Transport()
    service = OAuthClientService(
        token_endpoint="https://nebula.example/token",
        facade=facade,
        identity=Identity(),
        transport=transport,
        cache=MemoryOAuthTokenCache(),
        events=NullEventSink(),
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )

    colon = OAuthTokenRequest(resource="https://provider", scopes=("parking:search",))
    dot = OAuthTokenRequest(resource="https://provider", scopes=("parking.search",))

    first = await service.token(colon)
    second = await service.token(colon)
    await service.token(dot)

    assert first is second
    assert transport.calls == 2
    assert facade.token_calls == 2
