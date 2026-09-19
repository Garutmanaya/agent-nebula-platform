"""Common plugin composition used by embedded and standalone presets."""

from __future__ import annotations

from collections.abc import Iterable

from agent_nebula_platform.a2ui.plugin import A2UIPlugin
from agent_nebula_platform.a2ui.session.plugin import A2UISessionPlugin
from agent_nebula_platform.integrations.nebula.onboarding.plugin import OnboardingPlugin
from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.platform.lifecycle.agent_server_plugin import (
    AgentServerPlugin,
)
from agent_nebula_platform.platform.metrics.plugin import MetricsPlugin
from agent_nebula_platform.platform.plugins import RuntimePlugin
from agent_nebula_platform.platform.presets.models import (
    EmbeddedPresetOptions,
    RuntimeFeatureComponents,
)
from agent_nebula_platform.platform.scheduler.plugin import SchedulerPlugin
from agent_nebula_platform.platform.telemetry.plugin import TelemetryPlugin
from agent_nebula_platform.protocols.a2a import (
    A2AOAuth2ProtectedResourceAuthenticator,
    A2AServerSecurityService,
)
from agent_nebula_platform.protocols.a2a.server.plugin import A2AServerPlugin
from agent_nebula_platform.security.oauth.client.plugin import OAuthClientPlugin
from agent_nebula_platform.security.oauth.protected_resource.plugin import (
    ProtectedResourcePlugin,
)
from agent_nebula_platform.skills.plugin import SkillsPlugin


def compose_feature_plugins(
    *,
    components: RuntimeFeatureComponents,
    server: EmbeddedPresetOptions,
    leading_plugins: Iterable[RuntimePlugin] = (),
) -> tuple[RuntimePlugin, ...]:
    """Compose enabled plugins in dependency-safe initialization order.

    Automatic settings instantiate only capabilities represented by supplied
    components. Explicitly enabled capabilities fail closed when a required
    component is absent; explicitly disabled capabilities are omitted even when
    the caller supplied compatible components.
    """

    plugins: list[RuntimePlugin] = list(leading_plugins)
    settings = server.plugins

    metrics_available = components.metrics_registry is not None
    metrics_enabled = (
        metrics_available if settings.metrics is None else settings.metrics
    )
    if metrics_enabled:
        plugins.append(
            MetricsPlugin(
                components.metrics_registry,
                required=settings.metrics is True,
            )
        )

    telemetry_available = bool(components.telemetry_sinks)
    telemetry_enabled = (
        telemetry_available if settings.telemetry is None else settings.telemetry
    )
    if telemetry_enabled:
        plugins.append(
            TelemetryPlugin(
                components.telemetry_sinks,
                required=settings.telemetry is True,
            )
        )

    scheduler_available = bool(components.scheduled_jobs)
    scheduler_enabled = (
        scheduler_available if settings.scheduler is None else settings.scheduler
    )
    if scheduler_enabled:
        plugins.append(
            SchedulerPlugin(
                components.scheduled_jobs,
                required=settings.scheduler is True,
            )
        )

    onboarding_available = components.onboarding_settings is not None
    onboarding_enabled = _resolve_toggle(
        name="onboarding",
        configured=settings.onboarding,
        available=onboarding_available,
    )
    if onboarding_enabled:
        if components.onboarding_payload_provider is None:
            raise ConfigurationError(
                "Onboarding payload provider is required when onboarding is enabled"
            )
        plugins.append(
            OnboardingPlugin(
                settings=components.onboarding_settings,
                payload_provider=components.onboarding_payload_provider,
            )
        )

    registration_available = components.oauth_client_registration is not None
    registration_enabled = _resolve_toggle(
        name="oauth_client_registration",
        configured=settings.oauth_client_registration,
        available=registration_available,
    )
    if registration_enabled:
        assert components.oauth_client_registration is not None
        plugins.append(components.oauth_client_registration)

    if _resolve_toggle(
        name="oauth_client",
        configured=settings.oauth_client,
        available=components.oauth_client is not None,
    ):
        plugins.append(OAuthClientPlugin(components.oauth_client))

    if _resolve_toggle(
        name="a2ui_session",
        configured=settings.a2ui_session,
        available=components.a2ui_session is not None,
    ):
        plugins.append(
            A2UISessionPlugin(
                components.a2ui_session,
                dispatcher=components.a2ui_action_dispatcher,
            )
        )

    if _resolve_toggle(
        name="protected_resource",
        configured=settings.protected_resource,
        available=components.protected_resource is not None,
    ):
        plugins.append(ProtectedResourcePlugin(components.protected_resource))

    skills_enabled = _resolve_toggle(
        name="skills",
        configured=settings.skills,
        available=bool(components.skill_definitions),
    )
    metadata_enabled = _resolve_toggle(
        name="protected_resource_metadata",
        configured=settings.protected_resource_metadata,
        available=components.protected_resource_metadata is not None,
    )
    health_enabled = _resolve_toggle(
        name="health",
        configured=settings.health,
        available=components.health is not None,
    )

    if skills_enabled:
        plugins.append(
            SkillsPlugin(
                definitions=components.skill_definitions,
                metadata_provider=(
                    components.protected_resource_metadata if metadata_enabled else None
                ),
            )
        )

    rest_available = skills_enabled and server.enable_rest
    rest_enabled = _resolve_toggle(
        name="rest",
        configured=settings.rest,
        available=rest_available,
    )
    official_a2a_available = (
        components.a2a_agent_card is not None
        and components.a2a_request_handler is not None
        and server.enable_a2a
    )
    a2a_enabled = _resolve_toggle(
        name="a2a",
        configured=settings.a2a,
        available=official_a2a_available,
    )
    a2ui_available = bool(components.a2ui_allowed_components) and skills_enabled
    a2ui_enabled = _resolve_toggle(
        name="a2ui",
        configured=settings.a2ui,
        available=a2ui_available and server.enable_a2ui,
    )

    if a2a_enabled and official_a2a_available:
        assert components.a2a_agent_card is not None
        assert components.a2a_request_handler is not None
        authenticators = list(components.a2a_security_authenticators)
        configured_types = {item.scheme_type for item in authenticators}
        if (
            components.protected_resource is not None
            and "oauth2_security_scheme" not in configured_types
        ):
            authenticators.append(
                A2AOAuth2ProtectedResourceAuthenticator(components.protected_resource)
            )
        security = A2AServerSecurityService(
            agent_card=components.a2a_agent_card,
            authenticators=tuple(authenticators),
        )
        plugins.append(
            A2AServerPlugin(
                app=server.app,
                agent_card=components.a2a_agent_card,
                agent_card_route=components.a2a_agent_card_route,
                request_handler=components.a2a_request_handler,
                required=settings.a2a is True,
                security=security,
                tls=components.a2a_server_tls,
            )
        )

    if a2ui_enabled:
        plugins.append(
            A2UIPlugin(
                allowed_components=components.a2ui_allowed_components,
                allowed_functions=components.a2ui_allowed_functions,
                allowed_catalog_ids=components.a2ui_allowed_catalog_ids,
                supported_versions=components.a2ui_supported_versions,
                preferred_version=components.a2ui_preferred_version,
            )
        )

    plugins.append(
        AgentServerPlugin(
            app=server.app,
            protected_resource_metadata=(
                components.protected_resource_metadata if metadata_enabled else None
            ),
            health=components.health if health_enabled else None,
            health_routes=components.health_routes if health_enabled else None,
            enable_rest=rest_enabled,
            enable_a2ui=a2ui_enabled,
            api_prefix=server.api_prefix,
            trust_forwarded_headers=server.trust_forwarded_headers,
            forwarded_prefix_header=server.forwarded_prefix_header,
        )
    )
    return tuple(plugins)


def _resolve_toggle(
    *,
    name: str,
    configured: bool | None,
    available: bool,
) -> bool:
    """Resolve automatic capability selection and fail on invalid enablement."""

    if configured is False:
        return False
    if configured is True and not available:
        raise ConfigurationError(
            f"Runtime capability '{name}' is enabled but required components are absent"
        )
    return available if configured is None else configured
