from inspect import signature
from pathlib import Path

from agent_nebula_platform.protocols.a2a.client.client_configuration import (
    A2AClientOAuthConfiguration,
    A2AClientTlsConfiguration,
)
from agent_nebula_platform.protocols.a2a.client.discovered_oauth import (
    A2ADiscoveredOAuth2CredentialProvider,
)


def test_discovered_oauth_does_not_accept_registry_resource_override() -> None:
    assert "resource" not in signature(A2ADiscoveredOAuth2CredentialProvider).parameters

    provider = A2ADiscoveredOAuth2CredentialProvider(
        configuration=A2AClientOAuthConfiguration(
            client_id_file=Path("client-id"),
            authentication_private_key_file=Path("auth.pem"),
            dpop_private_key_file=Path("dpop.pem"),
        ),
        tls=A2AClientTlsConfiguration(),
        timeout_seconds=30,
    )

    assert not hasattr(provider, "_resource_override")
