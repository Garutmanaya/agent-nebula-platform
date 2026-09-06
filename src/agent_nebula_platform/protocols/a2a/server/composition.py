"""Standalone A2A server composition owned entirely by Agent Nebula Platform."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

from agent_nebula_platform.integrations.nebula.configuration import NebulaConfiguration
from agent_nebula_platform.integrations.nebula.onboarding import (
    OnboardingSettings,
    build_agent_onboarding_payload,
)
from agent_nebula_platform.platform.configuration.application import (
    PlatformApplicationConfigurationLoader,
)
from agent_nebula_platform.platform.health import StaticHealthProvider
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
from agent_nebula_platform.platform.presets.standalone.settings import (
    StandaloneServerSettings,
)
from agent_nebula_platform.platform.presets.standalone.application import StandaloneAgent
from agent_nebula_platform.protocols.a2a.server.configuration import (
    A2AServerConfigurationService,
)
from agent_nebula_platform.protocols.a2a.server.configuration.listener import (
    A2AListenerConfigurationLoader,
)
from agent_nebula_platform.protocols.a2a.server.execution import A2AExecutableSkill, A2AAgentExecutor
from agent_nebula_platform.protocols.a2a.security.protected_resource import (
    A2AProtectedResourceComposition,
    A2AProtectedResourceFactory,
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
        skill: A2AExecutableSkill,
        nebula_config: Path | None = None,
    ) -> A2AStandaloneApplication:
        """Build a standalone A2A application without developer-facade logic."""

        card = A2AServerConfigurationService().load_agent_card(server_config)
        configured_skill_ids = {published.id for published in card.skills}
        if skill.skill_id not in configured_skill_ids:
            from agent_nebula_platform.platform.errors import ConfigurationError

            raise ConfigurationError(
                f"Skill '{skill.skill_id}' is not published by a2aserver.conf"
            )
        listener = A2AListenerConfigurationLoader().load(server_config)
        handler = DefaultRequestHandler(
            agent_executor=A2AAgentExecutor(skill),
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
            capabilities=tuple(published.id for published in card.skills),
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
                tls_enabled=listener.certificate_file is not None,
                ssl_certificate_file=listener.certificate_file,
                ssl_private_key_file=listener.private_key_file,
            ),
            nebula=nebula_settings,
            state=StandaloneStateSettings(directory=application.runtime_root / "state"),
            logging=StandaloneLoggingSettings(logger_name="agent_nebula_platform"),
            plugins=StandalonePluginSettings(
                onboarding=bool(nebula and nebula.registration.enabled),
                oauth_client=False,
                protected_resource=protected_resource is not None,
                skills=False,
                protected_resource_metadata=False,
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
            onboarding_settings=onboarding_settings,
            onboarding_payload_provider=payload_provider,
            protected_resource=(
                protected_resource.runtime.service if protected_resource else None
            ),
            a2a_agent_card=card,
            a2a_request_handler=handler,
        )
        standalone = build_standalone_agent(settings=settings, components=components)
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
        capabilities: tuple[str, ...],
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
        payload = build_agent_onboarding_payload(
            entity_name=agent_name,
            agent_card_uri=A2AStandaloneApplicationComposer._agent_card_uri(interface_url),
            protocols=("A2A",),
            capabilities=capabilities,
            authentication_method=registration.authentication.value,
        )

        def payload_provider() -> dict:
            """Return the immutable registration payload for Runtime onboarding."""

            return payload

        return settings, onboarding, payload_provider

    @staticmethod
    def _agent_card_uri(interface_url: str) -> str:
        """Derive the standard public Agent Card URI from an A2A interface URL."""

        parsed = urlsplit(interface_url)
        return urlunsplit(
            (parsed.scheme, parsed.netloc, "/.well-known/agent-card.json", "", "")
        )
