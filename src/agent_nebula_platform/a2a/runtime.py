"""Platform Runtime composition for the native A2A SDK server.

This module intentionally depends on Platform presets. ``a2a.server`` does not,
so Runtime preset composition can safely import ``A2AServerPlugin`` without an
A2A server/preset circular import.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from a2a.server.request_handlers import RequestHandler
from fastapi import FastAPI

from agent_nebula_platform.a2a.extensions.health import ensure_health_extension
from agent_nebula_platform.a2a.security.server import A2AServerSecurityComposition
from agent_nebula_platform.integrations.nebula.configuration import NebulaConfiguration
from agent_nebula_platform.integrations.nebula.onboarding import (
    OnboardingSettings,
    build_agent_onboarding_payload,
    build_provider_onboarding_payload,
)
from agent_nebula_platform.integrations.nebula.transport import NebulaConnectorFactory
from agent_nebula_platform.platform.configuration.application import PlatformApplicationConfigurationLoader
from agent_nebula_platform.platform.health import HealthEndpointConfigurationLoader, StaticHealthProvider
from agent_nebula_platform.platform.metrics import MetricsRegistry
from agent_nebula_platform.platform.presets.standalone import (
    StandaloneApplicationSettings,
    StandaloneLoggingSettings,
    StandaloneNebulaSettings,
    StandalonePluginSettings,
    StandaloneRuntimeSettings,
    StandaloneStateSettings,
    build_standalone_agent,
)
from agent_nebula_platform.platform.presets.standalone.application import StandaloneAgent
from agent_nebula_platform.platform.presets.standalone.settings import StandaloneServerSettings
from agent_nebula_platform.platform.telemetry import ConsoleTelemetrySink

@dataclass(slots=True)
class A2APlatformRuntimeApplication:
    """Own the Platform Runtime surrounding one native a2a-sdk server."""

    application: StandaloneAgent
    protected_resource: object | None = None

    @property
    def app(self) -> FastAPI:
        return self.application.app

    def run(self) -> None:
        try:
            self.application.run()
        finally:
            if self.protected_resource is not None:
                self.protected_resource.runtime.transport.close()

    async def close(self) -> None:
        await self.application.runtime.close()
        if self.protected_resource is not None:
            await self.protected_resource.runtime.close()


class A2APlatformRuntimeComposer:
    """Restore Platform Runtime features around the migrated native A2A server.

    The migration intentionally removed duplicate A2A protocol abstractions, but
    the Platform Runtime is not an A2A abstraction. It is the security boundary
    for approved configuration paths and owns cross-cutting plugins such as
    Registry onboarding, health, metrics, telemetry, state and lifecycle.
    """

    def compose(
        self,
        *,
        application_config: Path,
        server_config: Path,
        nebula_config: Path | None,
        server_configuration,
        listener,
        request_handler: RequestHandler,
        security: A2AServerSecurityComposition,
    ) -> A2APlatformRuntimeApplication:
        card = server_configuration.agent_card
        application = PlatformApplicationConfigurationLoader().load(application_config)
        health_endpoints = HealthEndpointConfigurationLoader().load(server_config)
        if health_endpoints is not None:
            ensure_health_extension(card, health_endpoints)
        nebula = NebulaConfiguration.load(nebula_config) if nebula_config else None
        nebula_settings, onboarding_settings, payload_provider = self._nebula_components(
            nebula=nebula,
            agent_name=card.name,
            interface_url=str(card.supported_interfaces[0].url),
            agent_card_url=server_configuration.agent_card_url,
            capabilities=tuple(skill.id for skill in card.skills),
            protected_resource=security.protected_resource,
        )

        # Restore exactly the Runtime-owned plugins that the old protocols/a2a
        # composition enabled. They are independent of the A2A implementation.
        settings = StandaloneRuntimeSettings(
            application=StandaloneApplicationSettings(
                name=application.name,
                runtime_root=application.runtime_root,
                product_root=application.product_root,
            ),
            server=StandaloneServerSettings(
                host=listener.host,
                port=listener.port,
                enable_rest=False,
                enable_a2a=True,
                enable_a2ui=False,
                tls_enabled=listener.tls.enabled,
                ssl_certificate_file=listener.tls.certificate_file if listener.tls.enabled else None,
                ssl_private_key_file=listener.tls.private_key_file if listener.tls.enabled else None,
                ssl_trust_bundle_file=listener.tls.trust_bundle if listener.tls.enabled else None,
                ssl_require_client_certificate=listener.tls.require_client_certificate,
            ),
            nebula=nebula_settings,
            state=StandaloneStateSettings(directory=application.runtime_root / "state"),
            logging=StandaloneLoggingSettings(
                console_enabled=application.console_logging,
                logger_name="agent_nebula_platform",
                level=application.log_level,
            ),
            plugins=StandalonePluginSettings(
                onboarding=bool(nebula and nebula.registration.enabled),
                oauth_client=False,
                protected_resource=security.protected_resource is not None,
                skills=False,
                protected_resource_metadata=security.protected_resource is not None,
                health=True,
                rest=False,
                a2a=True,
                a2ui=False,
                a2ui_session=False,
                metrics=application.metrics,
                telemetry=application.telemetry,
                scheduler=False,
            ),
        )

        telemetry = (
            (ConsoleTelemetrySink(logging.getLogger("agent_nebula_platform")),)
            if application.telemetry
            else ()
        )
        # Import locally to keep the A2A integration independent of the preset
        # package initialization path. presets.models imports A2A configuration
        # types, so importing RuntimeFeatureComponents at module load would create
        # an a2a.server -> presets -> presets.models -> a2a cycle.
        from agent_nebula_platform.platform.presets.models import RuntimeFeatureComponents

        components = RuntimeFeatureComponents.create(
            health=StaticHealthProvider(),
            health_routes=health_endpoints.routes if health_endpoints is not None else None,
            onboarding_settings=onboarding_settings,
            onboarding_payload_provider=payload_provider,
            protected_resource=(
                security.protected_resource.runtime.service
                if security.protected_resource is not None
                else None
            ),
            protected_resource_metadata=(
                security.protected_resource.metadata
                if security.protected_resource is not None
                else None
            ),
            a2a_agent_card=card,
            a2a_agent_card_route=server_configuration.agent_card_route,
            a2a_request_handler=request_handler,
            a2a_server_tls=listener.tls,
            a2a_security_service=security.service,
            metrics_registry=MetricsRegistry() if application.metrics else None,
            telemetry_sinks=telemetry,
        )
        connector = NebulaConnectorFactory.create(nebula) if nebula is not None else None
        standalone = build_standalone_agent(
            settings=settings,
            components=components,
            nebula_connector=connector,
        )
        return A2APlatformRuntimeApplication(
            application=standalone,
            protected_resource=security.protected_resource,
        )

    @staticmethod
    def _nebula_components(
        *,
        nebula: NebulaConfiguration | None,
        agent_name: str,
        interface_url: str,
        agent_card_url: str,
        capabilities: tuple[str, ...],
        protected_resource,
    ):
        if nebula is None:
            return None, None, None
        settings = StandaloneNebulaSettings(
            base_url=nebula.base_url,
            ca_file=nebula.tls.ca_file,
            client_certificate_file=nebula.tls.client_certificate_file,
            client_private_key_file=nebula.tls.client_private_key_file,
            timeout_seconds=nebula.timeout_seconds,
        )
        registration = nebula.registration
        onboarding = OnboardingSettings(
            enabled=registration.enabled,
            state_key=registration.state_key,
            retry_count=registration.retry_count,
            retry_delay_seconds=registration.retry_delay_seconds,
            resolve_before_register=registration.resolve_before_register,
        )
        if protected_resource is None:
            payload = build_agent_onboarding_payload(
                entity_name=agent_name,
                agent_card_uri=agent_card_url,
                protocols=("A2A",),
                capabilities=capabilities,
                authentication_method=registration.authentication.value,
                external_agent_id=registration.external_agent_id,
            )
        else:
            document = protected_resource.metadata.get_protected_resource_metadata().copy_document()
            payload = build_provider_onboarding_payload(
                entity_name=agent_name,
                agent_card_uri=agent_card_url,
                protected_resource_metadata_uri=A2APlatformRuntimeComposer._protected_resource_metadata_uri(interface_url),
                protected_resource_document=document,
                protocols=("A2A",),
                capabilities=capabilities,
                authentication_method=registration.authentication.value,
                external_agent_id=registration.external_agent_id,
            )

        def payload_provider() -> dict:
            return payload

        return settings, onboarding, payload_provider

    @staticmethod
    def _protected_resource_metadata_uri(interface_url: str) -> str:
        parsed = urlsplit(interface_url)
        path = parsed.path.rstrip("/")
        return urlunsplit((parsed.scheme, parsed.netloc, f"{path}/.well-known/oauth-protected-resource", "", ""))
