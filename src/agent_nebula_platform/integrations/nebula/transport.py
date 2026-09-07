"""Managed Agent Nebula Registry transport composition.

All Registry-specific TLS and authentication handling belongs here. Runtime
presets and protocol adapters receive only the ``NebulaConnector`` contract and
must not duplicate Registry credential loading or HTTP header construction.
"""

from __future__ import annotations

import httpx

from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.platform.tls import FileTlsContextProvider

from .configuration import NebulaConfiguration, NebulaRegistrationAuthentication
from .connector import RestNebulaConnector


class NebulaConnectorFactory:
    """Create a managed Registry connector from validated ``nebula.conf`` settings."""

    @staticmethod
    def create(configuration: NebulaConfiguration) -> RestNebulaConnector:
        """Build one authenticated, verified Registry transport.

        API keys are transport credentials. They are deliberately loaded here
        and sent through ``X-API-Key`` rather than embedded in onboarding JSON.
        This keeps secret handling independent from protocol/onboarding payloads.
        """

        tls = configuration.tls
        context = FileTlsContextProvider(
            ca_file=tls.ca_file,
            certificate_file=tls.client_certificate_file,
            private_key_file=tls.client_private_key_file,
        ).create_client_context()
        client = httpx.AsyncClient(
            verify=context,
            timeout=httpx.Timeout(configuration.timeout_seconds),
            headers=NebulaConnectorFactory._authentication_headers(configuration),
        )
        return RestNebulaConnector(
            base_url=configuration.base_url,
            client=client,
            owns_client=True,
        )

    @staticmethod
    def _authentication_headers(configuration: NebulaConfiguration) -> dict[str, str]:
        registration = configuration.registration
        if registration.authentication is not NebulaRegistrationAuthentication.API_KEY:
            return {}

        # Pydantic validation guarantees the path is configured for API_KEY;
        # the transport boundary additionally validates the secret itself.
        assert registration.api_key_file is not None
        try:
            api_key = registration.api_key_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigurationError(
                "Nebula registration API key file cannot be read",
                details={"path": str(registration.api_key_file)},
            ) from exc
        if not api_key:
            raise ConfigurationError(
                "Nebula registration API key file is empty",
                details={"path": str(registration.api_key_file)},
            )
        return {"X-API-Key": api_key}
