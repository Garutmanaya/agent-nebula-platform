"""Role-neutral Runtime application settings and infrastructure composition."""

from __future__ import annotations

import logging
from configparser import ConfigParser
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from agent_nebula_sdk.oauth.client import OAuthClientFacade
from agent_nebula_sdk.oauth.rfc7523 import ClientAssertionBuilder, Rfc7523Policy
from agent_nebula_sdk.oauth.rfc8707 import ResourceParameterCodec
from agent_nebula_sdk.oauth.rfc9449 import (
    DpopProofBuilder,
    DpopTargetUriNormalizer,
    Rfc9449Policy,
)
from agent_nebula_sdk.ports.clock import SystemClock
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent_nebula_platform.a2ui.actions import A2UIActionDispatcher
from agent_nebula_platform.a2ui.session import (
    A2UISessionService,
    JsonFileA2UISessionStore,
    MemoryA2UISessionStore,
)
from agent_nebula_platform.integrations.nebula import RestNebulaConnector
from agent_nebula_platform.integrations.nebula.onboarding import OnboardingSettings
from agent_nebula_platform.platform.configuration import RuntimePathResolver
from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.discovery import NebulaDiscoveryClient
from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.platform.events import EventSink, NullEventSink
from agent_nebula_platform.platform.metrics import MetricsRegistry
from agent_nebula_platform.platform.presets.common import (
    ManagedResource,
    ManagedResourcesPlugin,
)
from agent_nebula_platform.platform.presets.composition import compose_feature_plugins
from agent_nebula_platform.platform.presets.logging import create_console_event_sink
from agent_nebula_platform.platform.presets.models import (
    EmbeddedPresetOptions,
    RuntimeFeatureComponents,
)
from agent_nebula_platform.platform.presets.standalone.settings import (
    StandaloneRuntimeSettings,
)
from agent_nebula_platform.platform.runtime import AgentRuntime
from agent_nebula_platform.platform.state import JsonFileStateStore
from agent_nebula_platform.platform.telemetry import ConsoleTelemetrySink
from agent_nebula_platform.platform.tls import FileTlsContextProvider
from agent_nebula_platform.platform.transport.fastapi import runtime_lifespan
from agent_nebula_platform.platform.transport.http_client import (
    RuntimeHttpClientFactory,
    RuntimeHttpClients,
)
from agent_nebula_platform.security.oauth.client import (
    HttpxOAuthTokenTransport,
    MemoryOAuthTokenCache,
    OAuthClientService,
    OnboardingOAuthClientIdentity,
    ProtectedHttpClient,
)
from agent_nebula_platform.security.oauth.protected_resource import (
    ProtectedResourceRuntime,
    ProtectedResourceRuntimeFactory,
    ProtectedResourceService,
)


class RuntimeRoleProfile(StrEnum):
    """Validated convenience profiles; explicit plugin settings remain authoritative."""

    PROVIDER = "PROVIDER"
    OAUTH_CLIENT = "OAUTH_CLIENT"
    ORCHESTRATOR = "ORCHESTRATOR"
    DUAL_ROLE = "DUAL_ROLE"


class RuntimeOnboardingSettings(BaseModel):
    """Define Runtime-managed onboarding identity and retry policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True
    authentication_method: str = Field(default="API_KEY", min_length=1)
    api_key_file: Path | None = None
    state_key: str = Field(default="runtime-onboarding", min_length=1)
    entity_name: str = Field(min_length=1)
    external_agent_id: str = Field(min_length=1)
    public_base_url: str = Field(min_length=1)
    retry_count: int = Field(default=10, ge=1, le=20)
    retry_delay_seconds: float = Field(default=3.0, ge=0, le=60)

    def plugin_settings(self) -> OnboardingSettings:
        """Convert application identity settings to plugin lifecycle settings."""

        return OnboardingSettings(
            enabled=self.enabled,
            state_key=self.state_key,
            retry_count=self.retry_count,
            retry_delay_seconds=self.retry_delay_seconds,
        )


class RuntimeOAuthClientSettings(BaseModel):
    """Define file-backed OAuth client and DPoP identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    token_endpoint: str = Field(min_length=1)
    client_id_file: Path | None = None
    registration_state_key: str | None = None
    authentication_private_key_file: Path
    dpop_private_key_file: Path
    key_id: str = Field(min_length=1)
    algorithm: str = Field(default="ES256", min_length=1)


class RuntimeProtectedResourceSettings(BaseModel):
    """Define provider-side SDK security composition inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    resource: str = Field(min_length=1)
    issuer: str = Field(min_length=1)
    jwks_uri: str = Field(min_length=1)
    access_token_algorithms: tuple[str, ...] = ("RS256",)
    dpop_algorithms: tuple[str, ...] = ("ES256",)
    dpop_required: bool = True
    timeout_seconds: float = Field(default=10.0, gt=0, le=300)
    jwks_cache_seconds: int = Field(default=300, ge=1)
    clock_skew_seconds: int = Field(default=30, ge=0)
    dpop_maximum_age_seconds: int = Field(default=300, ge=1)
    allow_private_jwks_networks: bool = True

    @field_validator("access_token_algorithms", "dpop_algorithms", mode="before")
    @classmethod
    def parse_algorithms(cls, value: object) -> object:
        """Accept comma-separated INI values while preserving tuple typing."""

        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value


class RuntimeA2UISessionSettings(BaseModel):
    """Configure Runtime-owned interactive A2UI session persistence."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True
    store: str = Field(default="json", pattern="^(json|memory)$")
    directory: Path | None = None
    max_history: int = Field(default=50, ge=1, le=500)
    max_actions: int = Field(default=200, ge=1, le=5000)


class RuntimeApplicationSettings(BaseModel):
    """Combine common infrastructure with optional role-specific capabilities."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    runtime: StandaloneRuntimeSettings
    role_profile: RuntimeRoleProfile | None = None
    onboarding: RuntimeOnboardingSettings | None = None
    oauth_client: RuntimeOAuthClientSettings | None = None
    protected_resource: RuntimeProtectedResourceSettings | None = None
    a2ui_session: RuntimeA2UISessionSettings | None = None

    def effective_runtime(self) -> StandaloneRuntimeSettings:
        """Apply role-profile defaults without overriding explicit plugin choices."""

        if self.role_profile is None:
            return self.runtime
        defaults: dict[RuntimeRoleProfile, dict[str, bool]] = {
            RuntimeRoleProfile.PROVIDER: {
                "onboarding": True,
                "oauth_client": False,
                "protected_resource": True,
                "skills": True,
                "protected_resource_metadata": True,
                "health": True,
                "rest": True,
                "a2a": True,
            },
            RuntimeRoleProfile.OAUTH_CLIENT: {
                "onboarding": True,
                "oauth_client": True,
                "protected_resource": False,
                "health": True,
            },
            RuntimeRoleProfile.ORCHESTRATOR: {
                "onboarding": True,
                "oauth_client": True,
                "protected_resource": False,
                "health": True,
                "metrics": True,
                "telemetry": True,
                "a2ui_session": True,
            },
            RuntimeRoleProfile.DUAL_ROLE: {
                "onboarding": True,
                "oauth_client": True,
                "protected_resource": True,
                "skills": True,
                "protected_resource_metadata": True,
                "health": True,
                "a2ui_session": True,
            },
        }
        current = self.runtime.plugins.model_dump()
        for name, value in defaults[self.role_profile].items():
            if current.get(name) is None:
                current[name] = value
        return self.runtime.model_copy(
            update={"plugins": self.runtime.plugins.model_copy(update=current)}
        )

    @model_validator(mode="after")
    def validate_enabled_capabilities(self) -> RuntimeApplicationSettings:
        """Require settings only for explicitly enabled role plugins."""

        plugins = self.effective_runtime().plugins
        if plugins.onboarding is True and self.onboarding is None:
            raise ValueError(
                "Onboarding settings are required when onboarding is enabled"
            )
        if (
            self.onboarding
            and self.onboarding.authentication_method.upper() != "OPEN"
            and self.onboarding.api_key_file is None
        ):
            raise ValueError("Runtime onboarding API key file is required")
        if plugins.oauth_client is True and self.oauth_client is None:
            raise ValueError(
                "OAuth client settings are required when oauth_client is enabled"
            )
        if plugins.protected_resource is True and self.protected_resource is None:
            raise ValueError(
                "Protected-resource settings are required when protected_resource is enabled"
            )
        if plugins.a2ui_session is True and self.a2ui_session is None:
            raise ValueError(
                "A2UI session settings are required when a2ui_session is enabled"
            )
        if (
            plugins.a2ui_session is True
            and self.a2ui_session
            and not self.a2ui_session.enabled
        ):
            raise ValueError(
                "A2UI session settings cannot be disabled while the plugin is enabled"
            )
        return self

    @classmethod
    def from_ini(cls, path: Path) -> RuntimeApplicationSettings:
        """Load all ``runtime.*`` sections through one Runtime-owned parser."""

        parser = ConfigParser(interpolation=None)
        if not parser.read(path):
            raise ConfigurationError(f"Unable to read Runtime configuration: {path}")

        def section(name: str) -> dict[str, str]:
            return dict(parser.items(name)) if parser.has_section(name) else {}

        application_section = section("runtime.application")
        role = application_section.pop("role_profile", None)
        runtime = StandaloneRuntimeSettings.model_validate(
            {
                "application": application_section,
                "server": section("runtime.server"),
                "nebula": section("runtime.nebula"),
                "state": section("runtime.state"),
                "logging": section("runtime.logging"),
                "plugins": section("runtime.plugins"),
            }
        )
        return cls(
            runtime=runtime,
            role_profile=RuntimeRoleProfile(role.upper()) if role else None,
            onboarding=RuntimeOnboardingSettings.model_validate(
                section("runtime.onboarding")
            )
            if parser.has_section("runtime.onboarding")
            else None,
            oauth_client=RuntimeOAuthClientSettings.model_validate(
                section("runtime.oauth_client")
            )
            if parser.has_section("runtime.oauth_client")
            else None,
            protected_resource=RuntimeProtectedResourceSettings.model_validate(
                section("runtime.protected_resource")
            )
            if parser.has_section("runtime.protected_resource")
            else None,
            a2ui_session=RuntimeA2UISessionSettings.model_validate(
                section("runtime.a2ui_session")
            )
            if parser.has_section("runtime.a2ui_session")
            else None,
        ).resolve_paths()

    def resolve_paths(self) -> RuntimeApplicationSettings:
        """Resolve paths according to Runtime-owned versus product-shared ownership."""

        runtime = self.effective_runtime().resolve_paths()
        resolver = RuntimePathResolver.create(
            runtime_root=runtime.application.runtime_root,
            product_root=runtime.application.product_root,
        )

        onboarding = self.onboarding
        oauth = self.oauth_client

        if onboarding:
            onboarding = onboarding.model_copy(
                update={"api_key_file": resolver.shared_path(onboarding.api_key_file)}
            )

        if oauth:
            oauth = oauth.model_copy(
                update={
                    "client_id_file": resolver.shared_path(oauth.client_id_file),
                    "authentication_private_key_file": resolver.shared_path(
                        oauth.authentication_private_key_file
                    ),
                    "dpop_private_key_file": resolver.shared_path(
                        oauth.dpop_private_key_file
                    ),
                }
            )

        a2ui_session = self.a2ui_session
        if a2ui_session:
            directory = (
                a2ui_session.directory or runtime.state.directory / "a2ui-sessions"
            )

            directory_path = Path(directory).expanduser()

            if not directory_path.is_absolute():
                # Preserve the original contract: relative A2UI session paths are
                # owned by the individual Runtime instance.
                resolved_directory = resolver.runtime_path(directory_path)
            else:
                runtime_root = runtime.application.runtime_root.resolve()
                product_root = runtime.application.product_root.resolve()
                absolute_directory = directory_path.resolve()

                if absolute_directory.is_relative_to(runtime_root):
                    resolved_directory = resolver.runtime_path(absolute_directory)
                elif absolute_directory.is_relative_to(product_root):
                    # Durable application state may live under product_root, such
                    # as Agent Studio orchestrator sessions.
                    resolved_directory = resolver.shared_path(absolute_directory)
                else:
                    # Delegate rejection to the existing Runtime resolver so the
                    # standard managed-path validation remains authoritative.
                    resolved_directory = resolver.runtime_path(absolute_directory)

            a2ui_session = a2ui_session.model_copy(
                update={"directory": resolved_directory}
            )

        return self.model_copy(
            update={
                "runtime": runtime,
                "onboarding": onboarding,
                "oauth_client": oauth,
                "a2ui_session": a2ui_session,
            }
        )

    def resolve_paths_old(self) -> RuntimeApplicationSettings:
        """Resolve paths according to Runtime-owned versus product-shared ownership."""

        runtime = self.effective_runtime().resolve_paths()
        resolver = RuntimePathResolver.create(
            runtime_root=runtime.application.runtime_root,
            product_root=runtime.application.product_root,
        )
        onboarding = self.onboarding
        oauth = self.oauth_client
        if onboarding:
            onboarding = onboarding.model_copy(
                update={"api_key_file": resolver.shared_path(onboarding.api_key_file)}
            )
        if oauth:
            oauth = oauth.model_copy(
                update={
                    "client_id_file": resolver.shared_path(oauth.client_id_file),
                    "authentication_private_key_file": resolver.shared_path(
                        oauth.authentication_private_key_file
                    ),
                    "dpop_private_key_file": resolver.shared_path(
                        oauth.dpop_private_key_file
                    ),
                }
            )
        a2ui_session = self.a2ui_session
        if a2ui_session:
            directory = a2ui_session.directory or (
                runtime.state.directory / "a2ui-sessions"
            )
            a2ui_session = a2ui_session.model_copy(
                update={"directory": resolver.runtime_path(directory)}
            )
        return self.model_copy(
            update={
                "runtime": runtime,
                "onboarding": onboarding,
                "oauth_client": oauth,
                "a2ui_session": a2ui_session,
            }
        )


@dataclass(slots=True)
class RuntimeApplicationServices:
    """Expose Runtime-owned capabilities to application business logic."""

    settings: RuntimeApplicationSettings
    context: RuntimeContext
    discovery: NebulaDiscoveryClient
    http_clients: RuntimeHttpClients
    metrics_registry: MetricsRegistry
    telemetry_sinks: tuple[ConsoleTelemetrySink, ...]
    oauth_client: OAuthClientService | None = None
    oauth_identity: OnboardingOAuthClientIdentity | None = None
    protected_http: ProtectedHttpClient | None = None
    protected_resource: ProtectedResourceService | None = None
    protected_resource_runtime: ProtectedResourceRuntime | None = None
    a2ui_sessions: A2UISessionService | None = None
    a2ui_actions: A2UIActionDispatcher | None = None


@dataclass(slots=True)
class RuntimeApplication:
    """Own a composed Agent Runtime, server configuration, and resources."""

    runtime: AgentRuntime
    services: RuntimeApplicationServices

    def run(self, app: FastAPI) -> None:
        """Run the configured HTTPS server with Runtime lifecycle ownership."""

        from agent_nebula_platform.platform.transport.fastapi import (
            UvicornRuntimeServer,
            UvicornServerSettings,
        )

        server = self.services.settings.runtime.server
        UvicornRuntimeServer(
            app=app,
            runtime=self.runtime,
            settings=UvicornServerSettings(
                host=server.host,
                port=server.port,
                certificate_file=server.ssl_certificate_file,
                private_key_file=server.ssl_private_key_file,
                console_logging=self.services.settings.runtime.logging.console_enabled,
                log_level=self.services.settings.runtime.logging.level,
            ),
        ).run()

    async def close(self) -> None:
        """Close plugins and Runtime-managed resources."""
        await self.runtime.close()


class RuntimeApplicationBuilder:
    """Build common and role-specific services strictly from enabled plugins."""

    def build_services(
        self, settings: RuntimeApplicationSettings
    ) -> RuntimeApplicationServices:
        """Create common infrastructure and only enabled role capabilities."""

        resolved = settings.resolve_paths()
        runtime = resolved.runtime
        tls_context = FileTlsContextProvider(
            ca_file=runtime.nebula.ca_file,
            certificate_file=runtime.nebula.client_certificate_file,
            private_key_file=runtime.nebula.client_private_key_file,
        ).create_client_context()
        api_key = self._read_api_key(resolved)
        clients = RuntimeHttpClientFactory(
            tls_context=tls_context, timeout_seconds=runtime.nebula.timeout_seconds
        ).create(nebula_headers={"X-API-Key": api_key} if api_key else {})
        connector = RestNebulaConnector(
            base_url=runtime.nebula.base_url, client=clients.nebula
        )
        events, telemetry = self._observability(runtime)
        state_store = JsonFileStateStore(runtime.state.directory)
        context = RuntimeContext(
            nebula=connector, state_store=state_store, events=events
        )
        services = RuntimeApplicationServices(
            settings=resolved,
            context=context,
            discovery=NebulaDiscoveryClient(context),
            http_clients=clients,
            metrics_registry=MetricsRegistry(),
            telemetry_sinks=telemetry,
        )
        if (
            runtime.plugins.oauth_client is not False
            and resolved.oauth_client is not None
        ):
            identity = OnboardingOAuthClientIdentity(
                state_store=state_store,
                onboarding_state_key=resolved.onboarding.state_key
                if resolved.onboarding
                else "runtime-onboarding",
                registration_state_key=resolved.oauth_client.registration_state_key,
                client_id_file=resolved.oauth_client.client_id_file,
                authentication_key_file=resolved.oauth_client.authentication_private_key_file,
                dpop_key_file=resolved.oauth_client.dpop_private_key_file,
                key_id=resolved.oauth_client.key_id,
                algorithm=resolved.oauth_client.algorithm,
            )
            services.oauth_identity = identity
            services.oauth_client = self._build_oauth_service(
                resolved.oauth_client, identity, clients, events
            )
            services.protected_http = ProtectedHttpClient(
                client=clients.provider,
                oauth=services.oauth_client,
            )
        if (
            runtime.plugins.a2ui_session is not False
            and resolved.a2ui_session is not None
            and resolved.a2ui_session.enabled
        ):
            session_settings = resolved.a2ui_session
            session_store = (
                MemoryA2UISessionStore()
                if session_settings.store == "memory"
                else JsonFileA2UISessionStore(session_settings.directory)
            )
            services.a2ui_sessions = A2UISessionService(
                store=session_store,
                events=events,
                max_history=session_settings.max_history,
                max_actions=session_settings.max_actions,
            )
            services.a2ui_actions = A2UIActionDispatcher(services.a2ui_sessions)
        if (
            runtime.plugins.protected_resource is not False
            and resolved.protected_resource is not None
        ):
            pr = resolved.protected_resource
            owned = ProtectedResourceRuntimeFactory().build(
                resource=pr.resource,
                issuer=pr.issuer,
                jwks_uri=pr.jwks_uri,
                ca_file=str(runtime.nebula.ca_file),
                access_token_algorithms=pr.access_token_algorithms,
                dpop_algorithms=pr.dpop_algorithms,
                events=events,
                dpop_required=pr.dpop_required,
                timeout_seconds=pr.timeout_seconds,
                jwks_cache_seconds=pr.jwks_cache_seconds,
                clock_skew_seconds=pr.clock_skew_seconds,
                dpop_maximum_age_seconds=pr.dpop_maximum_age_seconds,
                allow_private_jwks_networks=pr.allow_private_jwks_networks,
            )
            services.protected_resource_runtime = owned
            services.protected_resource = owned.service
        return services

    def attach(
        self,
        *,
        services: RuntimeApplicationServices,
        app: FastAPI,
        components: RuntimeFeatureComponents,
    ) -> RuntimeApplication:
        """Attach Runtime-owned role services and application business components."""

        settings = services.settings.runtime
        merged = replace(
            components,
            onboarding_settings=(
                services.settings.onboarding.plugin_settings()
                if services.settings.onboarding
                else components.onboarding_settings
            ),
            oauth_client=services.oauth_client or components.oauth_client,
            protected_resource=(
                services.protected_resource or components.protected_resource
            ),
            a2ui_session=(services.a2ui_sessions or components.a2ui_session),
            a2ui_action_dispatcher=(
                services.a2ui_actions or components.a2ui_action_dispatcher
            ),
            metrics_registry=(components.metrics_registry or services.metrics_registry),
            telemetry_sinks=(components.telemetry_sinks or services.telemetry_sinks),
        )
        resources = [
            ManagedResource(name="httpx.runtime", close=services.http_clients.close)
        ]
        if services.protected_resource_runtime is not None:
            resources.append(
                ManagedResource(
                    name="oauth.protected_resource.transport",
                    close=services.protected_resource_runtime.close,
                )
            )
        leading_plugins = [ManagedResourcesPlugin(resources)]
        plugins = compose_feature_plugins(
            components=merged,
            server=EmbeddedPresetOptions(
                app=app,
                enable_rest=settings.server.enable_rest,
                enable_a2a=settings.server.enable_a2a,
                enable_a2ui=settings.server.enable_a2ui,
                api_prefix=settings.server.api_prefix,
                trust_forwarded_headers=settings.server.trust_forwarded_headers,
                forwarded_prefix_header=settings.server.forwarded_prefix_header,
                plugins=settings.plugins.to_runtime_settings(),
            ),
            leading_plugins=tuple(leading_plugins),
        )
        runtime = AgentRuntime(context=services.context, plugins=plugins)
        app.router.lifespan_context = runtime_lifespan(runtime)
        return RuntimeApplication(runtime=runtime, services=services)

    @staticmethod
    def _observability(
        runtime: StandaloneRuntimeSettings,
    ) -> tuple[EventSink, tuple[ConsoleTelemetrySink, ...]]:
        if not runtime.logging.console_enabled:
            return NullEventSink(), ()
        events = create_console_event_sink(
            logger_name=runtime.logging.logger_name,
            level=getattr(logging, runtime.logging.level),
        )
        return events, (
            ConsoleTelemetrySink(logging.getLogger(runtime.logging.logger_name)),
        )

    @staticmethod
    def _read_api_key(settings: RuntimeApplicationSettings) -> str | None:
        onboarding = settings.onboarding
        if onboarding is None or onboarding.authentication_method.upper() == "OPEN":
            return None
        path = onboarding.api_key_file
        if path is None or not path.is_file():
            raise ConfigurationError(
                f"Runtime onboarding API key file does not exist: {path}"
            )
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            raise ConfigurationError(
                f"Runtime onboarding API key file is empty: {path}"
            )
        return value

    @staticmethod
    def _build_oauth_service(
        settings: RuntimeOAuthClientSettings,
        identity: OnboardingOAuthClientIdentity,
        clients: RuntimeHttpClients,
        events: EventSink,
    ) -> OAuthClientService:
        """Compose OAuth and DPoP exclusively from SDK primitives."""

        clock = SystemClock()
        dpop_policy = Rfc9449Policy(allowed_algorithms=frozenset({settings.algorithm}))
        facade = OAuthClientFacade(
            assertion_builder=ClientAssertionBuilder(
                clock=clock,
                policy=Rfc7523Policy(
                    allowed_algorithms=frozenset({settings.algorithm})
                ),
            ),
            resource_codec=ResourceParameterCodec(),
            dpop_builder=DpopProofBuilder(
                clock=clock,
                policy=dpop_policy,
                uri_normalizer=DpopTargetUriNormalizer(policy=dpop_policy),
            ),
        )
        return OAuthClientService(
            token_endpoint=settings.token_endpoint,
            facade=facade,
            identity=identity,
            transport=HttpxOAuthTokenTransport(clients.nebula),
            cache=MemoryOAuthTokenCache(),
            events=events,
        )
