"""Shared typed inputs for embedded and standalone runtime presets."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from a2a.server.request_handlers import RequestHandler
from a2a.types import AgentCard as OfficialA2AAgentCard
from fastapi import FastAPI

from agent_nebula_platform.a2ui import (
    A2UI_STABLE_VERSION,
    A2UI_SUPPORTED_VERSIONS,
)
from agent_nebula_platform.a2ui.actions import A2UIActionDispatcher
from agent_nebula_platform.a2ui.session import A2UISessionService
from agent_nebula_platform.integrations.nebula.onboarding import OnboardingSettings
from agent_nebula_platform.platform.health import HealthProvider, HealthRoutes
from agent_nebula_platform.platform.metrics import MetricsRegistry
from agent_nebula_platform.platform.plugins.base import RuntimePlugin
from agent_nebula_platform.platform.scheduler import ScheduledJob
from agent_nebula_platform.platform.telemetry import TelemetrySink
from agent_nebula_platform.protocols.a2a import A2ASecuritySchemeAuthenticator
from agent_nebula_platform.protocols.a2a.server.configuration.listener import (
    A2AServerTlsConfiguration,
)
from agent_nebula_platform.security.oauth.client import OAuthClientService
from agent_nebula_platform.security.oauth.metadata import (
    ProtectedResourceMetadataProvider,
)
from agent_nebula_platform.security.oauth.protected_resource import (
    ProtectedResourceService,
)
from agent_nebula_platform.skills import SkillDefinition

OnboardingPayloadProvider = Callable[[], Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class RuntimePluginSettings:
    """Control optional preset capabilities without forcing host adoption.

    ``None`` means automatic composition based on supplied components.  ``True``
    requires the capability and fails closed when its dependencies are absent.
    ``False`` disables it even when compatible components were supplied.
    """

    onboarding: bool | None = None
    oauth_client_registration: bool | None = None
    oauth_client: bool | None = None
    protected_resource: bool | None = None
    skills: bool | None = None
    protected_resource_metadata: bool | None = None
    health: bool | None = None
    rest: bool | None = None
    a2a: bool | None = None
    a2ui: bool | None = None
    a2ui_session: bool | None = None
    metrics: bool | None = None
    telemetry: bool | None = None
    scheduler: bool | None = None


@dataclass(frozen=True, slots=True)
class RuntimeFeatureComponents:
    """Supply host-owned documents, skills, and precomposed security services.

    Presets assemble infrastructure and plugin order, but they do not recreate
    OAuth, JOSE, JWT, JWK, or DPoP behavior. Those services remain composed from
    ``agent-nebula-sdk`` and are injected here.
    """

    skill_definitions: tuple[SkillDefinition, ...] = ()
    protected_resource_metadata: ProtectedResourceMetadataProvider | None = None
    health: HealthProvider | None = None
    health_routes: HealthRoutes | None = None
    onboarding_settings: OnboardingSettings | None = None
    onboarding_payload_provider: OnboardingPayloadProvider | None = None
    oauth_client_registration: RuntimePlugin | None = None
    oauth_client: OAuthClientService | None = None
    protected_resource: ProtectedResourceService | None = None
    a2a_agent_card: OfficialA2AAgentCard | None = None
    a2a_agent_card_route: str = "/.well-known/agent-card.json"
    a2a_request_handler: RequestHandler | None = None
    a2a_server_tls: A2AServerTlsConfiguration | None = None
    a2a_security_authenticators: tuple[A2ASecuritySchemeAuthenticator, ...] = ()
    a2ui_allowed_components: tuple[str, ...] = ()
    a2ui_allowed_functions: tuple[str, ...] = ()
    a2ui_allowed_catalog_ids: tuple[str, ...] = ()
    a2ui_supported_versions: tuple[str, ...] = A2UI_SUPPORTED_VERSIONS
    a2ui_preferred_version: str = A2UI_STABLE_VERSION
    a2ui_session: A2UISessionService | None = None
    a2ui_action_dispatcher: A2UIActionDispatcher | None = None
    metrics_registry: MetricsRegistry | None = None
    telemetry_sinks: tuple[TelemetrySink, ...] = ()
    scheduled_jobs: tuple[ScheduledJob, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        skill_definitions: Iterable[SkillDefinition] = (),
        protected_resource_metadata: ProtectedResourceMetadataProvider | None = None,
        health: HealthProvider | None = None,
        health_routes: HealthRoutes | None = None,
        onboarding_settings: OnboardingSettings | None = None,
        onboarding_payload_provider: OnboardingPayloadProvider | None = None,
        oauth_client_registration: RuntimePlugin | None = None,
        oauth_client: OAuthClientService | None = None,
        protected_resource: ProtectedResourceService | None = None,
        a2a_agent_card: OfficialA2AAgentCard | None = None,
        a2a_agent_card_route: str = "/.well-known/agent-card.json",
        a2a_request_handler: RequestHandler | None = None,
        a2a_server_tls: A2AServerTlsConfiguration | None = None,
        a2a_security_authenticators: Iterable[A2ASecuritySchemeAuthenticator] = (),
        a2ui_allowed_components: Sequence[str] = (),
        a2ui_allowed_functions: Sequence[str] = (),
        a2ui_allowed_catalog_ids: Sequence[str] = (),
        a2ui_supported_versions: Sequence[str] = A2UI_SUPPORTED_VERSIONS,
        a2ui_preferred_version: str = A2UI_STABLE_VERSION,
        a2ui_session: A2UISessionService | None = None,
        a2ui_action_dispatcher: A2UIActionDispatcher | None = None,
        metrics_registry: MetricsRegistry | None = None,
        telemetry_sinks: Iterable[TelemetrySink] = (),
        scheduled_jobs: Iterable[ScheduledJob] = (),
    ) -> RuntimeFeatureComponents:
        """Create immutable preset inputs from ordinary iterables."""

        return cls(
            skill_definitions=tuple(skill_definitions),
            protected_resource_metadata=protected_resource_metadata,
            health=health,
            health_routes=health_routes,
            onboarding_settings=onboarding_settings,
            onboarding_payload_provider=onboarding_payload_provider,
            oauth_client_registration=oauth_client_registration,
            oauth_client=oauth_client,
            protected_resource=protected_resource,
            a2a_agent_card=a2a_agent_card,
            a2a_agent_card_route=a2a_agent_card_route,
            a2a_request_handler=a2a_request_handler,
            a2a_server_tls=a2a_server_tls,
            a2a_security_authenticators=tuple(a2a_security_authenticators),
            a2ui_allowed_components=tuple(a2ui_allowed_components),
            a2ui_allowed_functions=tuple(a2ui_allowed_functions),
            a2ui_allowed_catalog_ids=tuple(a2ui_allowed_catalog_ids),
            a2ui_supported_versions=tuple(a2ui_supported_versions),
            a2ui_preferred_version=a2ui_preferred_version,
            a2ui_session=a2ui_session,
            a2ui_action_dispatcher=a2ui_action_dispatcher,
            metrics_registry=metrics_registry,
            telemetry_sinks=tuple(telemetry_sinks),
            scheduled_jobs=tuple(scheduled_jobs),
        )


@dataclass(frozen=True, slots=True)
class EmbeddedPresetOptions:
    """Control which runtime endpoints are attached to an existing app."""

    app: FastAPI
    enable_rest: bool = True
    enable_a2a: bool = True
    enable_a2ui: bool = True
    api_prefix: str = "/api/v1"
    trust_forwarded_headers: bool = False
    forwarded_prefix_header: str = "X-Forwarded-Prefix"
    plugins: RuntimePluginSettings = RuntimePluginSettings()
