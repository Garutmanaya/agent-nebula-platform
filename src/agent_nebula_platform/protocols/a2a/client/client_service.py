"""Application service for dedicated A2A client configuration and construction."""

from __future__ import annotations

from pathlib import Path

from agent_nebula_platform.a2ui.configuration import A2UIConfiguration
from agent_nebula_platform.protocols.a2a.extensions.a2ui import A2UIClientExtension
from agent_nebula_platform.protocols.a2a.extensions.skill_selection import (
    SkillSelectionClientExtension,
)

from .client_adapter import A2AClientAdapter
from .client_configuration import A2AClientConfiguration, A2AClientConfigurationLoader
from .client_credentials import (
    A2AApiKeyCredentialProvider,
    A2AHttpCredentialProvider,
    A2AMutualTlsCredentialProvider,
    A2AOidcCredentialProvider,
    load_static_credentials,
)
from .client_security import A2AClientSecurityInterceptor, A2AClientSecurityResolver
from .discovered_oauth import A2ADiscoveredOAuth2CredentialProvider


class A2AClientServiceFactory:
    """Compose the native ``a2a-sdk`` client environment from configuration.

    AGENT NEBULA INTEGRATION:
    This factory owns only Nebula-added configuration and security composition.
    ``A2AClientAdapter.connect`` ultimately returns the official SDK ``Client``;
    standard A2A operations are never mirrored by this service.
    """

    def __init__(self, loader: A2AClientConfigurationLoader | None = None) -> None:
        self._loader = loader or A2AClientConfigurationLoader()

    def create(
        self,
        path: Path,
        *,
        a2ui_configuration: A2UIConfiguration | None = None,
    ) -> A2AClientAdapter:
        """Load ``a2aclient.conf`` and compose transport plus security negotiation.

        Remote A2A and security facts are deliberately not accepted here. The
        resolved Agent Card and standards-based security metadata are authoritative.
        """

        configuration = self._loader.load(path)
        return self.create_from_configuration(
            configuration,
            a2ui_configuration=a2ui_configuration,
        )

    @staticmethod
    def create_from_configuration(
        configuration: A2AClientConfiguration,
        *,
        a2ui_configuration: A2UIConfiguration | None = None,
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
        if configuration.oauth is not None:
            providers.append(
                A2ADiscoveredOAuth2CredentialProvider(
                    configuration=configuration.oauth,
                    tls=configuration.tls,
                    timeout_seconds=configuration.timeout_seconds,
                )
            )

        security = A2AClientSecurityInterceptor(
            A2AClientSecurityResolver(tuple(providers))
        )
        extensions = [SkillSelectionClientExtension()]
        if a2ui_configuration is not None:
            extensions.append(A2UIClientExtension(a2ui_configuration))
        return A2AClientAdapter(
            configuration,
            security_interceptor=security,
            extensions=tuple(extensions),
        )
