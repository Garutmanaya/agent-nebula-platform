"""OAuth 2.0 credential acquisition driven by the remote A2A 1.0 Agent Card."""

from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx
from agent_nebula_sdk.adapters.httpx_transport import HttpxTransport
from agent_nebula_sdk.jose.jwks.models import JwkSet
from agent_nebula_sdk.oauth.client import OAuthClientFacade
from agent_nebula_sdk.oauth.rfc7523 import ClientAssertionBuilder, Rfc7523Policy
from agent_nebula_sdk.oauth.rfc7591 import (
    ClientMetadata,
    DynamicClientRegistrationClient,
)
from agent_nebula_sdk.oauth.rfc8414 import AuthorizationServerMetadataClient
from agent_nebula_sdk.oauth.rfc8707 import ResourceParameterCodec
from agent_nebula_sdk.oauth.rfc9449 import (
    DpopProofBuilder,
    DpopTargetUriNormalizer,
    Rfc9449Policy,
)
from agent_nebula_sdk.ports.clock import SystemClock

from agent_nebula_platform.platform.errors import (
    AuthenticationError,
    ConfigurationError,
)
from agent_nebula_platform.platform.events import NullEventSink
from agent_nebula_platform.platform.state import MemoryStateStore
from agent_nebula_platform.security.oauth.client import (
    HttpxOAuthTokenTransport,
    MemoryOAuthTokenCache,
    OAuthClientService,
    OnboardingOAuthClientIdentity,
)

from .client_configuration import A2AClientOAuthConfiguration, A2AClientTlsConfiguration
from .client_security import A2AClientCredential, A2AClientSecurityRequest


class A2ADiscoveredOAuth2CredentialProvider:
    """Acquire OAuth credentials and lazily register an unprovisioned A2A caller."""

    scheme_type = "oauth2_security_scheme"

    def __init__(
        self,
        *,
        configuration: A2AClientOAuthConfiguration,
        tls: A2AClientTlsConfiguration,
        timeout_seconds: float,
    ) -> None:
        self._configuration = configuration
        self._tls = tls
        self._timeout_seconds = timeout_seconds
        self._services: dict[str, tuple[OAuthClientService, httpx.AsyncClient]] = {}
        self._registration_lock = asyncio.Lock()

    def can_satisfy(self, request: A2AClientSecurityRequest) -> bool:
        return request.scheme.oauth2_security_scheme.flows.HasField(
            "client_credentials"
        )

    async def acquire(self, request: A2AClientSecurityRequest) -> A2AClientCredential:
        resource = self._resource(request)
        return await self.acquire_for_request_target(
            request, http_method="POST", target_uri=resource
        )

    async def acquire_for_request_target(
        self, request: A2AClientSecurityRequest, *, http_method: str, target_uri: str
    ) -> A2AClientCredential:
        definition = request.scheme.oauth2_security_scheme
        if not definition.flows.HasField("client_credentials"):
            raise AuthenticationError(
                "A2A OAuth2 scheme does not advertise client credentials"
            )
        token_endpoint = definition.flows.client_credentials.token_url
        if not token_endpoint:
            raise ConfigurationError(
                "A2A OAuth2 client-credentials flow is missing token_url"
            )
        await self._ensure_client_registration(request)
        protected = await self._service(token_endpoint).protected_request(
            http_method=http_method,
            target_uri=target_uri,
            resource=self._resource(request),
            scopes=request.required_values,
        )
        return A2AClientCredential(headers=tuple(protected.headers.items()))

    async def close(self) -> None:
        clients = tuple(client for _, client in self._services.values())
        self._services.clear()
        for client in clients:
            await client.aclose()

    async def _ensure_client_registration(
        self, request: A2AClientSecurityRequest
    ) -> None:
        if self._read_client_id() is not None:
            return
        async with self._registration_lock:
            if self._read_client_id() is not None:
                return
            metadata_url = request.scheme.oauth2_security_scheme.oauth2_metadata_url
            if not metadata_url:
                raise ConfigurationError(
                    "A2A OAuth2 client registration requires oauth2_metadata_url when client_id is absent"
                )
            client_id = await asyncio.to_thread(self._register_client, metadata_url)
            self._write_client_id(client_id)

    def _register_client(self, metadata_url: str) -> str:
        """Use A2A-advertised RFC 8414 metadata to perform standard RFC 7591 DCR."""
        verify: str | bool = (
            str(self._tls.trust_bundle) if self._tls.trust_bundle else True
        )
        transport = HttpxTransport(verify=verify, timeout_seconds=self._timeout_seconds)
        try:
            server = AuthorizationServerMetadataClient(transport=transport).fetch_url(
                metadata_url
            )
            if not server.registration_endpoint:
                raise ConfigurationError(
                    "A2A OAuth Authorization Server metadata has no registration_endpoint"
                )
            identity = self._identity()
            metadata = ClientMetadata(
                client_name="Agent Nebula A2A Client",
                grant_types=("client_credentials",),
                response_types=(),
                token_endpoint_auth_method="private_key_jwt",
                jwks=JwkSet.model_validate(identity.public_jwks_document()),
            )
            response = DynamicClientRegistrationClient(
                endpoint=server.registration_endpoint,
                transport=transport,
            ).register(metadata)
            return response.client_id
        finally:
            transport.close()

    def _service(self, token_endpoint: str) -> OAuthClientService:
        cached = self._services.get(token_endpoint)
        if cached is not None:
            return cached[0]
        algorithm = self._configuration.algorithm
        identity = self._identity()
        verify: str | bool = (
            str(self._tls.trust_bundle) if self._tls.trust_bundle else True
        )
        client = httpx.AsyncClient(verify=verify, timeout=self._timeout_seconds)
        clock = SystemClock()
        dpop_policy = Rfc9449Policy(allowed_algorithms=frozenset({algorithm}))
        facade = OAuthClientFacade(
            assertion_builder=ClientAssertionBuilder(
                clock=clock,
                policy=Rfc7523Policy(allowed_algorithms=frozenset({algorithm})),
            ),
            resource_codec=ResourceParameterCodec(),
            dpop_builder=DpopProofBuilder(
                clock=clock,
                policy=dpop_policy,
                uri_normalizer=DpopTargetUriNormalizer(policy=dpop_policy),
            ),
        )
        service = OAuthClientService(
            token_endpoint=token_endpoint,
            facade=facade,
            identity=identity,
            transport=HttpxOAuthTokenTransport(client),
            cache=MemoryOAuthTokenCache(),
            events=NullEventSink(),
        )
        self._services[token_endpoint] = (service, client)
        return service

    def _identity(self) -> OnboardingOAuthClientIdentity:
        return OnboardingOAuthClientIdentity(
            state_store=MemoryStateStore(),
            onboarding_state_key="a2a-direct-oauth-client",
            client_id_file=self._configuration.client_id_file,
            authentication_key_file=self._configuration.authentication_private_key_file,
            dpop_key_file=self._configuration.dpop_private_key_file,
            key_id=self._configuration.key_id,
            algorithm=self._configuration.algorithm,
        )

    def _read_client_id(self) -> str | None:
        path = self._configuration.client_id_file
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8").strip() or None

    def _write_client_id(self, client_id: str) -> None:
        value = client_id.strip()
        if not value:
            raise ConfigurationError("OAuth registration returned an empty client_id")
        path: Path = self._configuration.client_id_file
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(f"{value}\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)

    @staticmethod
    def _resource(request: A2AClientSecurityRequest) -> str:
        interfaces = tuple(request.agent_card.supported_interfaces)
        if not interfaces:
            raise ConfigurationError("A2A Agent Card has no supported interface")
        parsed = urlsplit(interfaces[0].url)
        return urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")
        )
