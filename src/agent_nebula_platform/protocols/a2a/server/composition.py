"""Standalone A2A server composition owned entirely by Agent Nebula Platform."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

from agent_nebula_platform.a2ui.configuration import A2UIConfiguration
from agent_nebula_platform.integrations.nebula.configuration import NebulaConfiguration
from agent_nebula_platform.integrations.nebula.transport import NebulaConnectorFactory
from agent_nebula_platform.integrations.nebula.onboarding import (
    OnboardingSettings,
    build_agent_onboarding_payload,
    build_provider_onboarding_payload,
)
from agent_nebula_platform.platform.configuration.application import (
    PlatformApplicationConfigurationLoader,
)
from agent_nebula_platform.platform.health import (
    HealthEndpointConfigurationLoader,
    StaticHealthProvider,
)
from agent_nebula_platform.platform.presets import RuntimeFeatureComponents
from agent_nebula_platform.platform.presets.standalone import (
    StandaloneApplicationSettings,
    StandaloneLoggingSettings,
    StandaloneNebulaSettings,
    StandalonePluginSettings,
    StandaloneRuntimeSettings,
    StandaloneStateSettings,
    build_standalone_agent,
)
from agent_nebula_platform.platform.presets.standalone.application import (
    StandaloneAgent,
)
from agent_nebula_platform.platform.presets.standalone.settings import (
    StandaloneServerSettings,
)
from agent_nebula_platform.protocols.a2a.extensions.a2ui import ensure_a2ui_extension
from agent_nebula_platform.protocols.a2a.extensions import (
    ensure_health_extension,
    ensure_schema_contract_extension,
    ensure_skill_selection_extension,
    validate_executable_skills,
)
from agent_nebula_platform.protocols.a2a.security.protected_resource import (
    A2AProtectedResourceComposition,
    A2AProtectedResourceFactory,
)
from agent_nebula_platform.protocols.a2a.server.configuration import (
    A2AServerConfigurationService,
)
from agent_nebula_platform.protocols.a2a.server.configuration.listener import (
    A2AListenerConfigurationLoader,
)
from agent_nebula_platform.protocols.a2a.server.execution import (
    A2AAgentExecutor,
    A2AExecutableSkill,
    A2UIActionHandler,
)


@dataclass(slots=True)
class A2AStandaloneApplication:
    """Own a composed standalone A2A application and security resources."""

    application: StandaloneAgent
    protected_resource: A2AProtectedResourceComposition | None = None

    @property
    def app(self):
        """Expose the FastAPI application created by the standalone preset."""

        return self.application.app

    def run(self) -> None:
        """Run the listener and release synchronous security transports on exit."""

        try:
            self.application.run()
        finally:
            if self.protected_resource is not None:
                self.protected_resource.runtime.transport.close()

    async def close(self) -> None:
        """Close Platform lifecycle and A2A security resources."""

        await self.application.runtime.close()
        if self.protected_resource is not None:
            await self.protected_resource.runtime.close()


class A2AStandaloneApplicationComposer:
    """Compose an A2A server from Platform configuration and a business skill.

    The composer contains the infrastructure wiring previously performed by the
    developer facade.  Callers provide configuration locations and business
    behavior; Platform owns A2A parsing, official request-handler construction,
    OAuth protected-resource composition, optional Nebula onboarding, and
    standalone lifecycle wiring.
    """

    def __init__(
        self,
        *,
        protected_resource_factory: A2AProtectedResourceFactory | None = None,
    ) -> None:
        """Accept replaceable factories for security composition and testing."""

        self._protected_resource_factory = (
            protected_resource_factory or A2AProtectedResourceFactory()
        )

    def compose(
        self,
        *,
        application_config: Path,
        server_config: Path,
        skill: A2AExecutableSkill | None = None,
        skills: tuple[A2AExecutableSkill, ...] = (),
        nebula_config: Path | None = None,
        a2ui: A2UIConfiguration | None = None,
        a2ui_action_handler: A2UIActionHandler | None = None,
    ) -> A2AStandaloneApplication:
        """Build a standalone A2A application without developer-facade logic."""

        server_configuration = A2AServerConfigurationService().load(server_config)
        card = server_configuration.agent_card
        health_endpoints = HealthEndpointConfigurationLoader().load(server_config)
        # Backward compatibility keeps the former single ``skill`` composition
        # call valid while SecureAgent migrates to passing all registered skills.
        executable_skills = skills or ((skill,) if skill is not None else ())
        validate_executable_skills(
            card, tuple(executable.skill_id for executable in executable_skills)
        )

        # NEBULA A2A EXTENSION: deterministic skill selection is an optional
        # capability. Generic A2A clients remain interoperable and may send
        # ordinary messages without activating Agent Nebula extension metadata.
        ensure_skill_selection_extension(card, required=False)

        # A2A Schema Contract Draft 0.1 uses the standard A2A 1.0 extension
        # mechanism; it does not add fields to AgentSkill or other core models.
        ensure_schema_contract_extension(card, executable_skills)

        # NEBULA A2A EXTENSION: operational health is independently configured
        # and advertised. It never changes A2A invocation semantics.
        if health_endpoints is not None:
            ensure_health_extension(card, health_endpoints)

        # A2UI is configured independently from A2A. The composer receives an
        # explicit A2UI configuration location and delegates only Agent Card
        # representation to the A2UI/A2A extension adapter.
        if a2ui is not None and a2ui.enabled:
            ensure_a2ui_extension(
                card,
                supported_catalog_ids=a2ui.supported_catalog_ids,
                accepts_inline_catalogs=a2ui.accepts_inline_catalogs,
            )

        listener = A2AListenerConfigurationLoader().load(server_config)
        handler = DefaultRequestHandler(
            agent_executor=A2AAgentExecutor(
                executable_skills,
                a2ui_action_handler=a2ui_action_handler,
            ),
            task_store=InMemoryTaskStore(),
            agent_card=card,
        )
        protected_resource = self._protected_resource_factory.create(
            agent_card=card,
            trust_bundle_file=listener.trust_bundle_file,
        )
        nebula = NebulaConfiguration.load(nebula_config) if nebula_config else None
        nebula_settings, onboarding_settings, payload_provider = self._nebula_components(
            nebula=nebula,
            agent_name=card.name,
            interface_url=str(card.supported_interfaces[0].url),
            agent_card_url=server_configuration.agent_card_url,
            capabilities=tuple(published.id for published in card.skills),
            protected_resource=protected_resource,
        )
        application = PlatformApplicationConfigurationLoader().load(application_config)
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
                ssl_certificate_file=(
                    listener.tls.certificate_file if listener.tls.enabled else None
                ),
                ssl_private_key_file=(
                    listener.tls.private_key_file if listener.tls.enabled else None
                ),
                ssl_trust_bundle_file=(
                    listener.tls.trust_bundle if listener.tls.enabled else None
                ),
            ),
            nebula=nebula_settings,
            state=StandaloneStateSettings(directory=application.runtime_root / "state"),
            logging=StandaloneLoggingSettings(logger_name="agent_nebula_platform"),
            plugins=StandalonePluginSettings(
                onboarding=bool(nebula and nebula.registration.enabled),
                oauth_client=False,
                protected_resource=protected_resource is not None,
                skills=False,
                protected_resource_metadata=protected_resource is not None,
                health=True,
                rest=False,
                a2a=True,
                a2ui=False,
                a2ui_session=False,
                metrics=False,
                telemetry=False,
                scheduler=False,
            ),
        )
        components = RuntimeFeatureComponents.create(
            health=StaticHealthProvider(),
            health_routes=health_endpoints.routes if health_endpoints is not None else None,
            onboarding_settings=onboarding_settings,
            onboarding_payload_provider=payload_provider,
            protected_resource=(
                protected_resource.runtime.service if protected_resource else None
            ),
            protected_resource_metadata=(
                protected_resource.metadata if protected_resource else None
            ),
            a2a_agent_card=card,
            a2a_agent_card_route=server_configuration.agent_card_route,
            a2a_request_handler=handler,
            a2a_server_tls=listener.tls,
        )
        nebula_connector = (
            NebulaConnectorFactory.create(nebula) if nebula is not None else None
        )
        standalone = build_standalone_agent(
            settings=settings,
            components=components,
            nebula_connector=nebula_connector,
        )
        return A2AStandaloneApplication(
            application=standalone,
            protected_resource=protected_resource,
        )

    @staticmethod
    def _nebula_components(
        *,
        nebula: NebulaConfiguration | None,
        agent_name: str,
        interface_url: str,
        agent_card_url: str,
        capabilities: tuple[str, ...],
        protected_resource: A2AProtectedResourceComposition | None,
    ) -> tuple[
        StandaloneNebulaSettings | None,
        OnboardingSettings | None,
        object | None,
    ]:
        """Translate optional Registry configuration into generic Platform inputs."""

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
        agent_card_uri = agent_card_url
        if protected_resource is None:
            payload = build_agent_onboarding_payload(
                entity_name=agent_name,
                agent_card_uri=agent_card_uri,
                protocols=("A2A",),
                capabilities=capabilities,
                authentication_method=registration.authentication.value,
                external_agent_id=registration.external_agent_id,
            )
        else:
            # OAuth protection is described using RFC 9728 and registered as a
            # separate onboarding concern.  We deliberately do not modify the
            # official A2A 1.0 Agent Card or the A2UI 1.0 extension to carry
            # Agent Nebula Registry data.  The document comes from the same
            # protected-resource composition that enforces OAuth at runtime.
            protected_resource_document = (
                protected_resource.metadata
                .get_protected_resource_metadata()
                .copy_document()
            )
            payload = build_provider_onboarding_payload(
                entity_name=agent_name,
                agent_card_uri=agent_card_uri,
                protected_resource_metadata_uri=(
                    A2AStandaloneApplicationComposer._protected_resource_metadata_uri(
                        interface_url
                    )
                ),
                protected_resource_document=protected_resource_document,
                protocols=("A2A",),
                capabilities=capabilities,
                authentication_method=registration.authentication.value,
                external_agent_id=registration.external_agent_id,
            )

        def payload_provider() -> dict:
            """Return the immutable registration payload for Runtime onboarding."""

            return payload

        return settings, onboarding, payload_provider

    @staticmethod
    def _protected_resource_metadata_uri(interface_url: str) -> str:
        """Derive the RFC 9728 metadata URI from the public A2A interface.

        Reverse-proxy path prefixes are part of the public resource namespace
        and must be preserved, exactly as they are for the Agent Card URI.
        """

        parsed = urlsplit(interface_url)
        public_path = parsed.path.rstrip("/")
        metadata_path = f"{public_path}/.well-known/oauth-protected-resource"
        return urlunsplit((parsed.scheme, parsed.netloc, metadata_path, "", ""))
