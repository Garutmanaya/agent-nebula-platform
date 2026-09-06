"""A2A server listener configuration owned by the A2A protocol module.

The official Agent Card is parsed by :mod:`agent_nebula_platform.protocols.a2a`
configuration services.  This module owns only listener/TLS settings that are
specific to hosting an A2A server.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from agent_nebula_platform.platform.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class A2AListenerConfiguration:
    """Resolved network and TLS settings for one A2A server listener."""

    host: str
    port: int
    certificate_file: Path | None
    private_key_file: Path | None
    trust_bundle_file: Path | None


class A2AListenerConfigurationLoader:
    """Load A2A listener settings without exposing TOML parsing to callers."""

    def load(self, path: Path) -> A2AListenerConfiguration:
        """Parse and validate the ``[server]`` section of ``a2aserver.conf``."""

        try:
            with path.open("rb") as stream:
                document = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigurationError(f"Invalid A2A server configuration: {path}") from exc
        server = document.get("server", {})
        if not isinstance(server, dict):
            raise ConfigurationError("a2aserver.conf [server] must be a table")
        certificate = self._path(server.get("tls_certificate_file"), path.parent)
        private_key = self._path(server.get("tls_private_key_file"), path.parent)
        if (certificate is None) != (private_key is None):
            raise ConfigurationError(
                "a2aserver.conf must configure TLS certificate and private key together"
            )
        return A2AListenerConfiguration(
            host=str(server.get("host", "0.0.0.0")),
            port=int(server.get("port", 9999)),
            certificate_file=certificate,
            private_key_file=private_key,
            trust_bundle_file=self._path(
                server.get("tls_trust_bundle_file"), path.parent
            ),
        )

    @staticmethod
    def _path(value: object, root: Path) -> Path | None:
        """Resolve an optional listener path relative to its configuration file."""

        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError("A2A server TLS paths must be non-empty strings")
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        return candidate.resolve()
