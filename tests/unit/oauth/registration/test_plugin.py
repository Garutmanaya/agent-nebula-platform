"""Tests for Runtime RFC 7591 registration composition."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from agent_nebula_sdk.oauth.rfc7591 import ClientMetadata, RegistrationResponse
from agent_nebula_sdk.ports.http import HttpResponse

from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.events import NullEventSink
from agent_nebula_platform.platform.state import MemoryStateStore
from agent_nebula_platform.security.oauth.registration.plugin import (
    OAuthClientRegistrationPlugin,
)
from agent_nebula_platform.security.oauth.registration.transport import (
    EnterpriseRegistrationHttpTransport,
)


class _NebulaConnector:
    """Unused Registry connector satisfying the Runtime context contract."""

    async def resolve_onboarding(self, payload):
        """Return no onboarding resolution."""

        del payload

    async def onboard(self, payload):
        """Reject unexpected onboarding calls in registration tests."""

        del payload
        raise AssertionError("onboarding connector should not be called")


class _RecordingTransport:
    """Record one RFC 7591 request for transport adapter tests."""

    def __init__(self) -> None:
        """Create an empty request record."""

        self.headers: dict[str, str] = {}

    def get(self, url, *, headers=None):
        """Return a placeholder GET response."""

        del url
        self.headers = dict(headers or {})
        return HttpResponse(200, {}, b"{}")

    def post(self, url, *, headers=None, body=b""):
        """Capture POST headers and return a minimal registration response."""

        del url, body
        self.headers = dict(headers or {})
        return HttpResponse(
            201, {}, b'{"client_id":"client-1","client_id_issued_at":1}'
        )

    def put(self, url, *, headers=None, body=b""):
        """Return a placeholder PUT response."""

        del url, body
        self.headers = dict(headers or {})
        return HttpResponse(200, {}, b"{}")

    def delete(self, url, *, headers=None):
        """Return a placeholder DELETE response."""

        del url
        self.headers = dict(headers or {})
        return HttpResponse(204, {}, b"")


def test_enterprise_transport_adds_api_key() -> None:
    """Add the Agent Nebula API key without removing RFC headers."""

    delegate = _RecordingTransport()
    transport = EnterpriseRegistrationHttpTransport(
        delegate=delegate, api_key="provider-key"
    )
    transport.post(
        "https://oauth.example/register", headers={"Content-Type": "application/json"}
    )
    assert delegate.headers["X-API-Key"] == "provider-key"
    assert delegate.headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_plugin_persists_authorization_server_client_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Persist the AS-issued client ID after enterprise enrollment verification."""

    api_key = tmp_path / "onboarding-api-key"
    api_key.write_text("provider-key", encoding="utf-8")
    state = MemoryStateStore()
    state.write(
        "onboarding",
        {
            "commit": {
                "profiles": {
                    "OAUTH_CLIENT": {
                        "client_enrollment_id": "enrollment-1",
                    }
                }
            }
        },
    )
    observed: dict[str, object] = {}

    class _Transport:
        """HTTP transport replacement used to avoid network access."""

        def __init__(self, **kwargs) -> None:
            """Capture TLS configuration."""

            observed["transport_kwargs"] = kwargs

        def post(self, url, *, headers=None, body=b""):
            """Capture the DCR request and return an AS-issued client ID."""

            observed["url"] = url
            observed["headers"] = dict(headers or {})
            observed["body"] = json.loads(body)
            return HttpResponse(
                201,
                {},
                b'{"client_id":"oauth-client-1","client_id_issued_at":1}',
            )

        def get(self, url, *, headers=None):
            """Reject unexpected GET calls."""

            raise AssertionError((url, headers))

        def put(self, url, *, headers=None, body=b""):
            """Reject unexpected PUT calls."""

            raise AssertionError((url, headers, body))

        def delete(self, url, *, headers=None):
            """Reject unexpected DELETE calls."""

            raise AssertionError((url, headers))

        def close(self) -> None:
            """Release no-op test resources."""

    monkeypatch.setattr(
        "agent_nebula_platform.security.oauth.registration.plugin.HttpxTransport",
        _Transport,
    )
    plugin = OAuthClientRegistrationPlugin(
        registration_endpoint="https://oauth.example/register",
        onboarding_state_key="onboarding",
        registration_state_key="registration",
        metadata_provider=lambda: ClientMetadata(
            client_name="Explorer",
            grant_types=("client_credentials",),
            response_types=(),
            token_endpoint_auth_method="private_key_jwt",
            jwks_uri="https://explorer.example/.well-known/jwks.json",
        ),
        api_key_file=api_key,
    )
    context = RuntimeContext(
        nebula=_NebulaConnector(),
        state_store=state,
        events=NullEventSink(),
    )

    await plugin.initialize(context)

    assert state.read("registration")["client_id"] == "oauth-client-1"
    assert observed["headers"]["X-API-Key"] == "provider-key"
    assert observed["body"]["nebula_enrollment_id"] == "enrollment-1"


@pytest.mark.asyncio
async def test_plugin_offloads_blocking_dcr_from_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run synchronous RFC 7591 registration outside the Runtime event-loop thread."""

    event_loop_thread = threading.get_ident()
    observed: dict[str, int] = {}

    class _Transport:
        """No-op transport used because the registration client is replaced below."""

        def __init__(self, **kwargs) -> None:
            """Accept normal transport construction arguments."""

            del kwargs

        def close(self) -> None:
            """Release no-op transport resources."""

    class _RegistrationClient:
        """Record the thread used by the synchronous SDK registration operation."""

        def __init__(self, *, endpoint, transport) -> None:
            """Accept the same construction contract as the SDK client."""

            del endpoint, transport

        def register(self, metadata):
            """Return a registration response and record the worker thread identifier."""

            del metadata
            observed["registration_thread"] = threading.get_ident()
            return RegistrationResponse(
                client_id="oauth-client-1", client_id_issued_at=1
            )

    monkeypatch.setattr(
        "agent_nebula_platform.security.oauth.registration.plugin.HttpxTransport",
        _Transport,
    )
    monkeypatch.setattr(
        "agent_nebula_platform.security.oauth.registration.plugin.DynamicClientRegistrationClient",
        _RegistrationClient,
    )

    plugin = OAuthClientRegistrationPlugin(
        registration_endpoint="https://oauth.example/register",
        onboarding_state_key="onboarding",
        registration_state_key="registration",
        metadata_provider=lambda: ClientMetadata(
            client_name="Explorer",
            grant_types=("client_credentials",),
            response_types=(),
            token_endpoint_auth_method="private_key_jwt",
            jwks_uri="https://explorer.example/.well-known/jwks.json",
        ),
    )
    context = RuntimeContext(
        nebula=_NebulaConnector(),
        state_store=MemoryStateStore(),
        events=NullEventSink(),
    )

    await plugin.initialize(context)

    assert observed["registration_thread"] != event_loop_thread
