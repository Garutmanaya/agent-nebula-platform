"""A2A server listener and transport TLS configuration."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from agent_nebula_platform.platform.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class A2AServerTlsConfiguration:
    """TLS mode and material shared by HTTP and gRPC A2A server bindings."""

    enabled: bool = False
    trust_bundle: Path | None = None
    certificate_file: Path | None = None
    private_key_file: Path | None = None


@dataclass(frozen=True, slots=True)
class A2AListenerConfiguration:
    """Resolved network and TLS settings for one A2A server listener."""

    host: str
    port: int
    tls: A2AServerTlsConfiguration

    @property
    def certificate_file(self) -> Path | None:
        return self.tls.certificate_file

    @property
    def private_key_file(self) -> Path | None:
        return self.tls.private_key_file

    @property
    def trust_bundle_file(self) -> Path | None:
        return self.tls.trust_bundle


class A2AListenerConfigurationLoader:
    """Load A2A listener settings without exposing TOML parsing to callers."""

    def load(self, path: Path) -> A2AListenerConfiguration:
        """Parse and validate ``[server]`` and ``[server.tls]``."""

        try:
            with path.open("rb") as stream:
                document = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigurationError(f"Invalid A2A server configuration: {path}") from exc
        server = document.get("server", {})
        if not isinstance(server, dict):
            raise ConfigurationError("a2aserver.conf [server] must be a table")

        tls_table = server.get("tls")
        if tls_table is None:
            # Preserve legacy files while new configurations migrate to [server.tls].
            tls_table = {
                "enabled": server.get("tls_certificate_file") is not None,
                "trust_bundle": server.get("tls_trust_bundle_file"),
                "certificate_file": server.get("tls_certificate_file"),
                "private_key_file": server.get("tls_private_key_file"),
            }
        elif not isinstance(tls_table, dict):
            raise ConfigurationError("a2aserver.conf [server.tls] must be a table")

        enabled = self._boolean(tls_table, "enabled", default=False)
        trust_bundle = self._path(tls_table.get("trust_bundle"), path.parent)
        certificate = self._path(tls_table.get("certificate_file"), path.parent)
        private_key = self._path(tls_table.get("private_key_file"), path.parent)
        if (certificate is None) != (private_key is None):
            raise ConfigurationError(
                "A2A server TLS certificate_file and private_key_file must be configured together"
            )
        if enabled and (certificate is None or private_key is None):
            raise ConfigurationError(
                "TLS-enabled A2A server requires certificate_file and private_key_file"
            )
        if not enabled and any(
            item is not None for item in (trust_bundle, certificate, private_key)
        ):
            raise ConfigurationError(
                "A2A server TLS material requires [server.tls].enabled = true"
            )
        return A2AListenerConfiguration(
            host=str(server.get("host", "0.0.0.0")),
            port=int(server.get("port", 9999)),
            tls=A2AServerTlsConfiguration(
                enabled=enabled,
                trust_bundle=trust_bundle,
                certificate_file=certificate,
                private_key_file=private_key,
            ),
        )

    @staticmethod
    def _boolean(document: dict[str, object], name: str, *, default: bool) -> bool:
        value = document.get(name, default)
        if not isinstance(value, bool):
            raise ConfigurationError(f"A2A server TLS {name} must be a boolean")
        return value

    @staticmethod
    def _path(value: object, root: Path) -> Path | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError("A2A server TLS paths must be non-empty strings")
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        return candidate.resolve()
