"""Optional Agent Nebula integration configuration.

This configuration is deliberately separate from A2A server/client configuration.
An A2A application has no Agent Nebula dependency unless ``nebula.conf`` is supplied.
"""

from __future__ import annotations

import configparser
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent_nebula_platform.platform.errors import ConfigurationError


class NebulaRegistrationAuthentication(StrEnum):
    """Registry onboarding authentication methods supported by Runtime."""

    OPEN = "OPEN"
    API_KEY = "API_KEY"


class NebulaTlsSettings(BaseModel):
    """Outbound Registry TLS policy. Verification cannot be disabled."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    mode: str = Field(default="full-verify", pattern="^full-verify$")
    ca_file: Path
    client_certificate_file: Path | None = None
    client_private_key_file: Path | None = None

    @model_validator(mode="after")
    def validate_client_identity_pair(self) -> NebulaTlsSettings:
        if (self.client_certificate_file is None) != (
            self.client_private_key_file is None
        ):
            raise ValueError(
                "Nebula TLS client certificate and private key must be supplied together"
            )
        return self


class NebulaRegistrationSettings(BaseModel):
    """Registry registration lifecycle independent from A2A authentication."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True
    authentication: NebulaRegistrationAuthentication = (
        NebulaRegistrationAuthentication.OPEN
    )
    api_key_file: Path | None = None
    state_key: str = Field(default="nebula-registration", min_length=1)
    retry_count: int = Field(default=3, ge=1, le=20)
    retry_delay_seconds: float = Field(default=1.0, ge=0, le=60)
    resolve_before_register: bool = True

    @model_validator(mode="after")
    def validate_authentication(self) -> NebulaRegistrationSettings:
        if (
            self.authentication is NebulaRegistrationAuthentication.API_KEY
            and self.api_key_file is None
        ):
            raise ValueError("API_KEY registration requires api_key_file")
        if (
            self.authentication is NebulaRegistrationAuthentication.OPEN
            and self.api_key_file is not None
        ):
            raise ValueError("OPEN registration must not configure api_key_file")
        return self


class NebulaConfiguration(BaseModel):
    """Complete optional Agent Nebula Registry integration settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    base_url: str = Field(min_length=1)
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    tls: NebulaTlsSettings
    registration: NebulaRegistrationSettings = NebulaRegistrationSettings()

    @classmethod
    def load(cls, path: Path) -> NebulaConfiguration:
        """Load ``nebula.conf`` and resolve file paths relative to its directory."""
        config_path = path.expanduser().resolve()
        parser = configparser.ConfigParser(interpolation=None)
        try:
            with config_path.open(encoding="utf-8") as stream:
                parser.read_file(stream)
        except (OSError, configparser.Error) as exc:
            raise ConfigurationError(
                "Nebula configuration file is invalid",
                details={"path": str(config_path)},
            ) from exc
        if not parser.has_section("nebula") or not parser.has_section("tls"):
            raise ConfigurationError("nebula.conf requires [nebula] and [tls] sections")
        nebula = dict(parser.items("nebula"))
        tls = dict(parser.items("tls"))
        registration = (
            dict(parser.items("registration"))
            if parser.has_section("registration")
            else {}
        )
        for key in ("enabled", "resolve_before_register"):
            if key in registration:
                registration[key] = parser.getboolean("registration", key)
        if "retry_count" in registration:
            registration["retry_count"] = int(registration["retry_count"])
        for section in (nebula, registration):
            for key in ("timeout_seconds", "retry_delay_seconds"):
                if key in section:
                    section[key] = float(section[key])
        root = config_path.parent
        for key in ("ca_file", "client_certificate_file", "client_private_key_file"):
            if tls.get(key):
                value = Path(tls[key]).expanduser()
                tls[key] = value if value.is_absolute() else (root / value).resolve()
        if registration.get("api_key_file"):
            value = Path(registration["api_key_file"]).expanduser()
            registration["api_key_file"] = (
                value if value.is_absolute() else (root / value).resolve()
            )
        return cls.model_validate({**nebula, "tls": tls, "registration": registration})
