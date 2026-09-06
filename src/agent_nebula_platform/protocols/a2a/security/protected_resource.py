"""A2A OAuth protected-resource composition from official Agent Card metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from a2a.types import AgentCard
from agent_nebula_sdk.adapters.httpx_transport import HttpxTransport
from agent_nebula_sdk.oauth.rfc8414 import AuthorizationServerMetadataClient

from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.platform.events import NullEventSink
from agent_nebula_platform.security.oauth.protected_resource.factory import (
    ProtectedResourceRuntime,
    ProtectedResourceRuntimeFactory,
)


@dataclass(frozen=True, slots=True)
class A2AProtectedResourceComposition:
    """Own the SDK-backed protected-resource runtime created for an A2A server."""

    runtime: ProtectedResourceRuntime


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
        protected = ProtectedResourceRuntimeFactory().build(
            resource=str(agent_card.supported_interfaces[0].url).rstrip("/"),
            issuer=metadata.issuer,
            jwks_uri=metadata.jwks_uri,
            ca_file=str(trust_bundle_file),
            access_token_algorithms=("RS256",),
            dpop_algorithms=("ES256",),
            events=NullEventSink(),
            timeout_seconds=timeout_seconds,
        )
        return A2AProtectedResourceComposition(runtime=protected)

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
