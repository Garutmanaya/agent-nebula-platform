"""A2A OAuth protected-resource composition from official Agent Card metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from a2a.types import AgentCard
from agent_nebula_sdk.adapters.httpx_transport import HttpxTransport
from agent_nebula_sdk.oauth.rfc8414 import AuthorizationServerMetadataClient

from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.platform.events import NullEventSink
from agent_nebula_platform.security.oauth.metadata import (
    AuthorizationServerMetadata,
    ProtectedResourceMetadataFactory,
    ProtectedResourceMetadataProvider,
)
from agent_nebula_platform.security.oauth.protected_resource.factory import (
    ProtectedResourceRuntime,
    ProtectedResourceRuntimeFactory,
)


@dataclass(frozen=True, slots=True)
class A2AProtectedResourceComposition:
    """Own OAuth runtime security and its authoritative RFC 9728 metadata.

    The runtime validates inbound OAuth/DPoP requests. ``metadata`` is the same
    protected-resource description used for discovery and Agent Nebula
    onboarding. Keeping both in one composition prevents registration metadata
    from drifting from the resource identifier and authorization server that
    actually protect the A2A endpoint.
    """

    runtime: ProtectedResourceRuntime
    metadata: ProtectedResourceMetadataProvider


class A2AProtectedResourceFactory:
    """Create OAuth validation only when an Agent Card advertises OAuth 2.0."""

    def create(
        self,
        *,
        agent_card: AgentCard,
        trust_bundle_file: Path | None,
        timeout_seconds: float = 10.0,
    ) -> A2AProtectedResourceComposition | None:
        """Resolve RFC 8414 metadata and compose the generic OAuth resource service."""

        metadata_urls = self._oauth_metadata_urls(agent_card)
        if not metadata_urls:
            return None
        if trust_bundle_file is None:
            raise ConfigurationError(
                "OAuth-protected A2A server requires [server.tls].trust_bundle in a2aserver.conf"
            )
        if len(metadata_urls) != 1:
            raise ConfigurationError(
                "A2A OAuth security schemes must advertise one common Authorization Server metadata URL"
            )
        transport = HttpxTransport(
            timeout_seconds=timeout_seconds,
            verify=str(trust_bundle_file),
        )
        try:
            metadata = AuthorizationServerMetadataClient(transport=transport).fetch_url(
                next(iter(metadata_urls))
            )
        finally:
            transport.close()
        if metadata.jwks_uri is None:
            raise ConfigurationError(
                "Authorization Server metadata for A2A OAuth protection is missing jwks_uri"
            )
        resource = str(agent_card.supported_interfaces[0].url).rstrip("/")
        protected = ProtectedResourceRuntimeFactory().build(
            resource=resource,
            issuer=metadata.issuer,
            jwks_uri=metadata.jwks_uri,
            ca_file=str(trust_bundle_file),
            access_token_algorithms=("RS256",),
            dpop_algorithms=("ES256",),
            events=NullEventSink(),
            timeout_seconds=timeout_seconds,
        )
        # RFC 9728 metadata is OAuth discovery metadata, not an A2A extension.
        # Derive it from the official A2A 1.0 Agent Card security schemes and
        # the same verified RFC 8414 document used by the runtime.  This keeps
        # A2A and A2UI protocol models untouched while making the protected
        # resource available to Registry onboarding and discovery.
        protected_resource_metadata = ProtectedResourceMetadataFactory().create(
            resource=resource,
            resource_name=agent_card.name,
            authorization_server=AuthorizationServerMetadata(
                issuer=metadata.issuer,
                jwks_uri=metadata.jwks_uri,
                token_endpoint=metadata.token_endpoint,
                registration_endpoint=metadata.registration_endpoint,
            ),
            scopes=self._oauth_scopes(agent_card),
            dpop_algorithms=("ES256",),
        )
        return A2AProtectedResourceComposition(
            runtime=protected,
            metadata=protected_resource_metadata,
        )

    @staticmethod
    def _oauth_scopes(agent_card: AgentCard) -> tuple[str, ...]:
        """Return OAuth scopes advertised by official A2A 1.0 security schemes.

        Scope identifiers remain owned by the Agent Card.  Platform only
        projects those standard OAuth flow values into RFC 9728 metadata; it
        does not add fields to the A2A Agent Card or reinterpret A2A skills.
        """

        scopes: list[str] = []
        for scheme in agent_card.security_schemes.values():
            if scheme.WhichOneof("scheme") != "oauth2_security_scheme":
                continue
            flows = scheme.oauth2_security_scheme.flows
            for _, flow in flows.ListFields():
                for scope in flow.scopes:
                    if scope not in scopes:
                        scopes.append(scope)
        return tuple(scopes)

    @staticmethod
    def _oauth_metadata_urls(agent_card: AgentCard) -> set[str]:
        """Return OAuth metadata URLs advertised by official A2A security schemes."""

        urls: set[str] = set()
        for scheme in agent_card.security_schemes.values():
            if scheme.WhichOneof("scheme") != "oauth2_security_scheme":
                continue
            metadata_url = scheme.oauth2_security_scheme.oauth2_metadata_url
            if not metadata_url:
                raise ConfigurationError(
                    "A2A OAuth2 security scheme requires oauth2_metadata_url for server validation"
                )
            urls.add(metadata_url)
        return urls
