"""Public health endpoint configuration for hosted agent runtimes."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from agent_nebula_platform.platform.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class HealthRoutes:
    """Define local HTTP routes for the health capability."""

    health: str = "/health"
    liveness: str = "/health/live"
    readiness: str = "/health/ready"


@dataclass(frozen=True, slots=True)
class HealthEndpointConfiguration:
    """Define independently advertised public health endpoints.

    Absolute URLs are configuration authority. Their path components are used
    only to mount the corresponding routes on the local HTTP application.
    """

    health_url: str
    liveness_url: str
    readiness_url: str

    @property
    def routes(self) -> HealthRoutes:
        """Translate public URLs into local server-root routes."""
        return HealthRoutes(
            health=urlparse(self.health_url).path,
            liveness=urlparse(self.liveness_url).path,
            readiness=urlparse(self.readiness_url).path,
        )


class HealthEndpointConfigurationLoader:
    """Load optional health publication settings from an agent server file."""

    def load(self, path: Path) -> HealthEndpointConfiguration | None:
        """Return configured health endpoints, or ``None`` when not advertised."""
        configuration_path = path.expanduser().resolve()
        try:
            with configuration_path.open("rb") as stream:
                document = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigurationError(
                "A2A server configuration file is invalid",
                details={"path": str(configuration_path)},
            ) from exc

        health = document.get("health")
        if health is None:
            return None
        if not isinstance(health, dict):
            raise ConfigurationError("A2A server [health] section must be a mapping")

        values = {
            "health_url": health.get("url"),
            "liveness_url": health.get("liveness_url"),
            "readiness_url": health.get("readiness_url"),
        }
        for name, value in values.items():
            self._validate_url(name, value)
        return HealthEndpointConfiguration(
            health_url=str(values["health_url"]).strip(),
            liveness_url=str(values["liveness_url"]).strip(),
            readiness_url=str(values["readiness_url"]).strip(),
        )

    @staticmethod
    def _validate_url(name: str, value: object) -> None:
        """Require an unambiguous absolute HTTP(S) publication URL."""
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(
                f"A2A server health.{name} must be a non-empty absolute HTTP(S) URL"
            )
        parsed = urlparse(value.strip())
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or not parsed.path.startswith("/")
            or parsed.query
            or parsed.fragment
        ):
            raise ConfigurationError(
                f"A2A server health.{name} must be an absolute HTTP(S) URL without query or fragment",
                details={"value": value},
            )
