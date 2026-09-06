"""Application service for dedicated A2A client configuration and construction."""

from __future__ import annotations

from pathlib import Path

from agent_nebula_platform.security.oauth.client.service import OAuthClientService

from .client_adapter import A2AClientAdapter
from .client_configuration import A2AClientConfiguration, A2AClientConfigurationLoader
from .client_credentials import (
    A2AApiKeyCredentialProvider,
    A2AHttpCredentialProvider,
    A2AMutualTlsCredentialProvider,
    A2AOAuth2CredentialProvider,
    A2AOidcCredentialProvider,
    load_static_credentials,
)
from .client_security import A2AClientSecurityInterceptor, A2AClientSecurityResolver
from .discovered_oauth import A2ADiscoveredOAuth2CredentialProvider


class A2AClientServiceFactory:
    """Create fully secured Platform A2A clients from external configuration.

    The factory is the composition boundary between Step 4 transport configuration
    and Step 5 security negotiation.  Callers do not need to know about individual
    A2A credential-provider classes.
    """

    def __init__(self, loader: A2AClientConfigurationLoader | None = None) -> None:
        self._loader = loader or A2AClientConfigurationLoader()

    def create(
        self,
        path: Path,
        *,
        oauth_service: OAuthClientService | None = None,
        resource: str | None = None,
    ) -> A2AClientAdapter:
        """Load ``a2aclient.conf`` and compose transport plus security negotiation.

        ``resource`` is the protected-resource identifier selected by discovery.
        It is deliberately supplied by the caller rather than inferred from an
        arbitrary Agent Card URL.  OAuth is available only when both a Platform
        OAuth client service and that resource identifier are present.
        """

        configuration = self._loader.load(path)
        return self.create_from_configuration(
            configuration,
            oauth_service=oauth_service,
            resource=resource,
        )

    @staticmethod
    def create_from_configuration(
        configuration: A2AClientConfiguration,
        *,
        oauth_service: OAuthClientService | None = None,
        resource: str | None = None,
    ) -> A2AClientAdapter:
        """Compose one official A2A client adapter from validated settings."""

        static_credentials = load_static_credentials(configuration)
        providers = [
            A2AApiKeyCredentialProvider(static_credentials),
            A2AHttpCredentialProvider(static_credentials),
            A2AOidcCredentialProvider(static_credentials),
            A2AMutualTlsCredentialProvider(
                identity_configured=(
                    configuration.tls.certificate_file is not None
                    and configuration.tls.private_key_file is not None
                )
            ),
        ]
        if oauth_service is not None and resource:
            providers.append(
                A2AOAuth2CredentialProvider(service=oauth_service, resource=resource)
            )
        elif configuration.oauth is not None:
            providers.append(
                A2ADiscoveredOAuth2CredentialProvider(
                    configuration=configuration.oauth,
                    tls=configuration.tls,
                    timeout_seconds=configuration.timeout_seconds,
                    resource=resource,
                )
            )

        security = A2AClientSecurityInterceptor(
            A2AClientSecurityResolver(tuple(providers))
        )
        return A2AClientAdapter(configuration, security_interceptor=security)
