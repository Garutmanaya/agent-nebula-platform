"""Typed standalone configuration with layered source precedence."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent_nebula_platform.platform.configuration import (
    LayeredSettingsLoader,
    RuntimeHome,
    RuntimePathResolver,
)
from agent_nebula_platform.platform.presets.models import RuntimePluginSettings


class StandaloneApplicationSettings(BaseModel):
    """Define the external root and local runtime identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(default="agent-runtime", min_length=1, max_length=200)
    runtime_root: Path
    product_root: Path | None = None


class StandaloneServerSettings(BaseModel):
    """Define the explicitly managed FastAPI/Uvicorn listener."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=8080, ge=1, le=65535)
    api_prefix: str = Field(default="/api/v1", min_length=1)
    enable_rest: bool = True
    enable_a2a: bool = True
    enable_a2ui: bool = True
    tls_enabled: bool = True
    trust_forwarded_headers: bool = False
    forwarded_prefix_header: str = "X-Forwarded-Prefix"
    ssl_certificate_file: Path | None = None
    ssl_private_key_file: Path | None = None
    ssl_trust_bundle_file: Path | None = None

    @model_validator(mode="after")
    def validate_tls_files(self) -> StandaloneServerSettings:
        """Require a certificate and key only when listener TLS is enabled."""

        if self.tls_enabled and (
            self.ssl_certificate_file is None or self.ssl_private_key_file is None
        ):
            raise ValueError(
                "TLS-enabled listeners require ssl_certificate_file and "
                "ssl_private_key_file"
            )
        return self


class StandaloneNebulaSettings(BaseModel):
    """Define Agent Nebula REST connectivity and verified client TLS files."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str = Field(min_length=1, max_length=4096)
    ca_file: Path
    client_certificate_file: Path | None = None
    client_private_key_file: Path | None = None
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)

    @model_validator(mode="after")
    def validate_mtls_pair(self) -> StandaloneNebulaSettings:
        """Require the outbound client certificate and key as one pair."""

        if (self.client_certificate_file is None) != (
            self.client_private_key_file is None
        ):
            raise ValueError(
                "Nebula client certificate and private key must be supplied together"
            )
        return self


class StandaloneStateSettings(BaseModel):
    """Define non-authoritative local cache storage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    directory: Path = Path("runtime/state")


class StandaloneLoggingSettings(BaseModel):
    """Define the isolated runtime event logger."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    console_enabled: bool = True
    logger_name: str = Field(default="agent_nebula_platform", min_length=1)
    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")


class StandalonePluginSettings(BaseModel):
    """Define explicit enable, disable, or automatic plugin composition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    def to_runtime_settings(self) -> RuntimePluginSettings:
        """Convert Pydantic configuration into the preset-neutral dataclass."""

        return RuntimePluginSettings(**self.model_dump())


class StandaloneRuntimeSettings(BaseModel):
    """Aggregate all built-in infrastructure settings for a standalone agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    application: StandaloneApplicationSettings
    server: StandaloneServerSettings
    nebula: StandaloneNebulaSettings | None = None
    state: StandaloneStateSettings = StandaloneStateSettings()
    logging: StandaloneLoggingSettings = StandaloneLoggingSettings()
    plugins: StandalonePluginSettings = StandalonePluginSettings()

    @classmethod
    def from_ini(cls, path: Path) -> StandaloneRuntimeSettings:
        """Load one INI file while preserving the historical explicit API."""

        environment = dict(os.environ)
        root = RuntimeHome.resolve(
            environment=environment,
            explicit_root=path.expanduser().resolve().parent.parent,
        )
        return cls.from_sources(
            config_path=path,
            environment=environment,
            runtime_home=root.root,
        )

    @classmethod
    def from_sources(
        cls,
        *,
        config_path: Path | None = None,
        environment: Mapping[str, str] | None = None,
        command_line: Mapping[str, Any] | Sequence[str] | None = None,
        runtime_home: Path | None = None,
    ) -> StandaloneRuntimeSettings:
        """Load built-ins, external configuration, environment, and CLI layers.

        Precedence is strictly:

        ``built-in defaults → configuration file → environment → CLI``.
        """

        env = dict(os.environ if environment is None else environment)
        home = RuntimeHome.resolve(environment=env, explicit_root=runtime_home)
        selected_config = config_path
        if selected_config is None:
            configured = env.get("AGENT_RUNTIME_CONFIG")
            selected_config = Path(configured) if configured else home.config_file()
        selected_config = selected_config.expanduser().resolve()

        defaults: dict[str, Any] = {
            "application": {
                "name": "agent-runtime",
                "runtime_root": str(home.root),
            },
            "server": {
                "host": "127.0.0.1",
                "port": 8080,
                "api_prefix": "/api/v1",
                "enable_rest": True,
                "enable_a2a": True,
                "enable_a2ui": True,
            },
            "state": {"directory": "runtime/state"},
            "logging": {
                "console_enabled": True,
                "logger_name": "agent_nebula_platform",
                "level": "INFO",
            },
            "plugins": {},
        }
        loaded = LayeredSettingsLoader().load(
            cls,
            defaults=defaults,
            config_file=selected_config,
            environment=env,
            command_line=command_line,
        )
        return loaded.resolve_paths()

    def resolve_paths(self) -> StandaloneRuntimeSettings:
        """Resolve fields according to application and product ownership."""

        resolver = RuntimePathResolver.create(
            runtime_root=self.application.runtime_root,
            product_root=self.application.product_root,
        )
        return self.model_copy(
            update={
                "application": self.application.model_copy(
                    update={
                        "runtime_root": resolver.runtime_root,
                        "product_root": resolver.product_root,
                    }
                ),
                "server": self.server.model_copy(
                    update={
                        "ssl_certificate_file": (
                            resolver.runtime_path(self.server.ssl_certificate_file)
                            if self.server.tls_enabled
                            else None
                        ),
                        "ssl_private_key_file": (
                            resolver.runtime_path(self.server.ssl_private_key_file)
                            if self.server.tls_enabled
                            else None
                        ),
                    }
                ),
                "nebula": (
                    self.nebula.model_copy(
                        update={
                            "ca_file": resolver.shared_path(self.nebula.ca_file),
                            "client_certificate_file": resolver.runtime_path(
                                self.nebula.client_certificate_file
                            ),
                            "client_private_key_file": resolver.runtime_path(
                                self.nebula.client_private_key_file
                            ),
                        }
                    )
                    if self.nebula is not None
                    else None
                ),
                "state": self.state.model_copy(
                    # State may be externalized beneath the product root so a
                    # replaceable container can recover onboarding and OAuth
                    # identity without weakening path containment.
                    update={"directory": resolver.shared_path(self.state.directory)}
                ),
            }
        )
