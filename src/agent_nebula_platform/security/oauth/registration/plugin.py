"""Post-server RFC 7591 registration plugin for OAuth client identities.

The plugin runs after Registry onboarding and after the local HTTPS listener is reachable so an
Authorization Server can resolve the caller's configured ``jwks_uri`` during registration.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent_nebula_sdk.adapters.httpx_transport import HttpxTransport
from agent_nebula_sdk.oauth.rfc7591 import (
    ClientMetadata,
    DynamicClientRegistrationClient,
    RegistrationResponse,
)

from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.events import RuntimeEvent
from agent_nebula_platform.platform.health import HealthStatus
from agent_nebula_platform.platform.plugins.base import (
    RuntimePlugin,
    RuntimePluginPhase,
)

from .transport import EnterpriseRegistrationHttpTransport

ClientMetadataProvider = Callable[[], ClientMetadata]


class OAuthClientRegistrationPlugin(RuntimePlugin):
    """Register an OAuth caller with the configured RFC 7591 Authorization Server."""

    def __init__(
        self,
        *,
        registration_endpoint: str,
        onboarding_state_key: str,
        registration_state_key: str,
        metadata_provider: ClientMetadataProvider,
        trust_bundle_file: Path | str | None = None,
        api_key_file: Path | str | None = None,
        required: bool = True,
    ) -> None:
        """Configure registration, Registry-state linkage, TLS, and optional Nebula trust."""

        self._registration_endpoint = str(registration_endpoint)
        self._onboarding_state_key = onboarding_state_key
        self._registration_state_key = registration_state_key
        self._metadata_provider = metadata_provider
        self._trust_bundle_file = Path(trust_bundle_file) if trust_bundle_file else None
        self._api_key_file = Path(api_key_file) if api_key_file else None
        self._required = required
        self.result: RegistrationResponse | None = None

    @property
    def name(self) -> str:
        """Return the stable runtime plugin identifier."""

        return "oauth.client.registration"

    @property
    def phase(self) -> RuntimePluginPhase:
        """Run DCR after the local HTTPS/JWKS endpoint is reachable."""

        return RuntimePluginPhase.POST_SERVER

    @property
    def required(self) -> bool:
        """Return whether registration failure must fail Runtime startup."""

        return self._required

    async def initialize(self, context: RuntimeContext) -> None:
        """Resolve Registry enrollment, perform RFC 7591 DCR, and cache the client ID."""

        cached = context.state_store.read(self._registration_state_key)
        if cached is not None and _client_id(cached) is not None:
            self.result = RegistrationResponse.model_validate(cached)
            return

        onboarding_state = context.state_store.read(self._onboarding_state_key)
        enrollment_id = _client_enrollment_id(onboarding_state)
        metadata = self._metadata_provider()

        api_key: str | None = None
        if enrollment_id is not None:
            metadata = _with_nebula_enrollment(metadata, enrollment_id)
            api_key = self._read_required_api_key()

        verify: bool | str = (
            str(self._trust_bundle_file)
            if self._trust_bundle_file is not None
            else True
        )
        transport = HttpxTransport(verify=verify)
        enterprise_transport = EnterpriseRegistrationHttpTransport(
            delegate=transport,
            api_key=api_key,
        )
        registration_client = DynamicClientRegistrationClient(
            endpoint=self._registration_endpoint,
            transport=enterprise_transport,
        )

        # RFC 7591 registration is implemented by the SDK as a synchronous operation.
        # This Runtime plugin, however, executes during the asynchronous POST_SERVER phase while
        # the local HTTPS listener is already serving Agent Card and JWKS endpoints. Enterprise
        # Agent Nebula DCR deliberately uses the caller's standard ``jwks_uri``. The external
        # Authorization Server can therefore call back to this Runtime's JWKS endpoint while the
        # original registration request is still in progress:
        #
        #     Runtime -> Authorization Server: RFC 7591 registration
        #     Authorization Server -> Runtime: GET /.well-known/jwks.json
        #
        # Calling the synchronous SDK client directly from this coroutine would block the Uvicorn
        # event-loop thread. The Runtime would then be unable to complete the Authorization
        # Server's JWKS callback, producing a circular wait that surfaces as a TLS/connect timeout.
        # Offloading only the blocking RFC 7591 call preserves the SDK's synchronous protocol API
        # while keeping the Runtime event loop available to serve the required callback.
        #
        # AGENT NEBULA ADDITIONAL FUNCTIONALITY: enterprise enrollment verification introduces the
        # callback dependency because the Authorization Server validates the registered key against
        # the Registry-owned CLIENT enrollment. This scheduling rule does not alter RFC 7591.
        try:
            response = await asyncio.to_thread(registration_client.register, metadata)
        finally:
            transport.close()

        self.result = response
        context.state_store.write(
            self._registration_state_key,
            response.model_dump(mode="json", exclude_none=True),
        )
        context.events.emit(
            RuntimeEvent(
                "oauth.client.registration.completed",
                {
                    "enterprise": enrollment_id is not None,
                    "registration_endpoint": self._registration_endpoint,
                },
            )
        )

    async def health(self) -> HealthStatus:
        """Report plugin liveness independently from registration completion."""

        return HealthStatus(status="healthy", ready=True)

    async def readiness(self) -> HealthStatus:
        """Remain unready until RFC 7591 registration has produced a client identifier."""

        if self.result is None:
            return HealthStatus(status="initializing", ready=False)
        return HealthStatus(status="ready", ready=True)

    def _read_required_api_key(self) -> str:
        """Read the Provider API key required by Agent Nebula enterprise DCR."""

        if self._api_key_file is None or not self._api_key_file.is_file():
            raise RuntimeError(
                "Agent Nebula enterprise OAuth registration requires an onboarding API key file"
            )
        value = self._api_key_file.read_text(encoding="utf-8").strip()
        if not value:
            raise RuntimeError("Agent Nebula onboarding API key file is empty")
        return value


def _with_nebula_enrollment(
    metadata: ClientMetadata, enrollment_id: str
) -> ClientMetadata:
    """Add the Agent Nebula enrollment extension without changing RFC 7591 SDK behavior.

    AGENT NEBULA ADDITIONAL FUNCTIONALITY: ``nebula_enrollment_id`` is product metadata accepted
    through RFC 7591's extension mechanism; it is not an OAuth standard metadata member.
    """

    payload = metadata.model_dump(mode="python", exclude_none=True)
    payload["nebula_enrollment_id"] = enrollment_id
    return ClientMetadata.model_validate(payload)


def _client_enrollment_id(state: dict[str, Any] | None) -> str | None:
    """Extract the Registry-owned enterprise CLIENT enrollment identifier."""

    if not state:
        return None

    direct = state.get("client_enrollment_id")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    commit = state.get("commit")
    if not isinstance(commit, dict):
        return None
    profiles = commit.get("profiles")
    if not isinstance(profiles, dict):
        return None
    profile = (
        profiles.get("OAUTH_CLIENT")
        or profiles.get("CLIENT")
        or profiles.get("oauth_client")
    )
    if not isinstance(profile, dict):
        return None

    value = profile.get("client_enrollment_id")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _client_id(state: dict[str, Any]) -> str | None:
    """Return a cached RFC 7591 client identifier when one is present."""

    value = state.get("client_id")
    return value.strip() if isinstance(value, str) and value.strip() else None
