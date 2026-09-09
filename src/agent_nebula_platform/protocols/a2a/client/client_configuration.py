"""Typed loading and validation for the dedicated A2A client configuration."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from a2a.utils.constants import TransportProtocol

from agent_nebula_platform.platform.errors import ConfigurationError

_SUPPORTED_BINDINGS = {
    TransportProtocol.JSONRPC,
    TransportProtocol.HTTP_JSON,
    TransportProtocol.GRPC,
}


@dataclass(frozen=True, slots=True)
class A2AClientTlsConfiguration:
    """TLS mode and material used by outbound A2A transports and Agent Card discovery."""

    enabled: bool = False
    trust_bundle: Path | None = None
    certificate_file: Path | None = None
    private_key_file: Path | None = None


@dataclass(frozen=True, slots=True)
class A2AClientCredentialConfiguration:
    """Local secret material keyed by arbitrary remote Agent Card scheme name."""

    scheme_name: str
    secret_file: Path


@dataclass(frozen=True, slots=True)
class A2AClientOAuthConfiguration:
    """Locally provisioned OAuth client identity used for discovered OAuth2 schemes."""

    client_id_file: Path
    authentication_private_key_file: Path
    dpop_private_key_file: Path
    key_id: str = "a2a-oauth-client"
    algorithm: str = "ES256"


@dataclass(frozen=True, slots=True)
class A2AClientConfiguration:
    """Platform-owned settings mapped to the official A2A ``ClientConfig``."""

    streaming: bool
    polling: bool
    supported_protocol_bindings: tuple[str, ...]
    use_client_preference: bool
    accepted_output_modes: tuple[str, ...]
    timeout_seconds: float
    agent_card_path: str | None
    tls: A2AClientTlsConfiguration
    credentials: tuple[A2AClientCredentialConfiguration, ...] = ()
    oauth: A2AClientOAuthConfiguration | None = None


class A2AClientConfigurationLoader:
    """Load ``a2aclient.conf`` without interpreting remote Agent Card security."""

    def load(self, path: Path) -> A2AClientConfiguration:
        """Parse and validate one dedicated A2A client TOML configuration file."""

        configuration_path = path.expanduser().resolve()
        if not configuration_path.is_file():
            raise ConfigurationError(
                "A2A client configuration file does not exist",
                details={"path": str(configuration_path)},
            )
        try:
            with configuration_path.open("rb") as stream:
                document = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigurationError(
                "A2A client configuration file is invalid",
                details={"path": str(configuration_path)},
            ) from exc

        client = self._require_table(document, "client")
        tls = self._require_table(client, "tls", parent="client")
        bindings = tuple(self._string_list(client, "supported_protocol_bindings"))
        if not bindings:
            raise ConfigurationError(
                "A2A client must configure at least one supported protocol binding"
            )
        unknown = sorted(set(bindings) - _SUPPORTED_BINDINGS)
        if unknown:
            raise ConfigurationError(
                "A2A client configuration contains unsupported protocol bindings",
                details={"bindings": unknown},
            )
        if len(set(bindings)) != len(bindings):
            raise ConfigurationError("A2A client protocol bindings must be unique")

        timeout = self._number(client, "timeout_seconds", default=30.0)
        if timeout <= 0:
            raise ConfigurationError(
                "A2A client timeout_seconds must be greater than zero"
            )

        tls_enabled = self._boolean(tls, "enabled", default=False)
        trust_bundle = self._optional_path(
            tls, "trust_bundle", configuration_path.parent
        )
        certificate_file = self._optional_path(
            tls, "certificate_file", configuration_path.parent
        )
        private_key_file = self._optional_path(
            tls, "private_key_file", configuration_path.parent
        )
        if (certificate_file is None) != (private_key_file is None):
            raise ConfigurationError(
                "A2A client TLS certificate_file and private_key_file must be configured together"
            )
        # A trust bundle controls certificate verification for outbound HTTPS
        # (Agent Card, OAuth metadata/token endpoints, and HTTP A2A bindings)
        # even when explicit client TLS/mTLS mode is disabled.  Requiring
        # ``enabled = true`` for a CA bundle made ordinary HTTPS callers either
        # reject valid private PKI configuration or fall back to disabled
        # verification.  Client certificate material remains explicit mTLS
        # configuration and therefore still requires TLS mode to be enabled.
        if not tls_enabled and (certificate_file is not None or private_key_file is not None):
            raise ConfigurationError(
                "A2A client certificate material requires [client.tls].enabled = true"
            )

        credentials_table = client.get("credentials", {})
        if not isinstance(credentials_table, dict):
            raise ConfigurationError("A2A client [client.credentials] must be a table")
        credentials: list[A2AClientCredentialConfiguration] = []
        for scheme_name, entry in credentials_table.items():
            if (
                not isinstance(scheme_name, str)
                or not scheme_name.strip()
                or not isinstance(entry, dict)
            ):
                raise ConfigurationError(
                    "A2A client credential entries must be named tables"
                )
            secret_file = self._required_path(
                entry, "secret_file", configuration_path.parent
            )
            credentials.append(
                A2AClientCredentialConfiguration(
                    scheme_name=scheme_name.strip(), secret_file=secret_file
                )
            )

        oauth_table = client.get("oauth")
        oauth = None
        if oauth_table is not None:
            if not isinstance(oauth_table, dict):
                raise ConfigurationError("A2A client [client.oauth] must be a table")
            oauth = A2AClientOAuthConfiguration(
                client_id_file=self._destination_path(
                    oauth_table, "client_id_file", configuration_path.parent
                ),
                authentication_private_key_file=self._required_path(
                    oauth_table,
                    "authentication_private_key_file",
                    configuration_path.parent,
                ),
                dpop_private_key_file=self._required_path(
                    oauth_table, "dpop_private_key_file", configuration_path.parent
                ),
                key_id=str(oauth_table.get("key_id", "a2a-oauth-client")).strip(),
                algorithm=str(oauth_table.get("algorithm", "ES256")).strip(),
            )
            if not oauth.key_id or not oauth.algorithm:
                raise ConfigurationError(
                    "A2A client OAuth key_id and algorithm must be non-empty"
                )

        agent_card_path = client.get("agent_card_path")
        if agent_card_path is not None:
            if not isinstance(agent_card_path, str) or not agent_card_path.strip():
                raise ConfigurationError(
                    "A2A client agent_card_path must be a non-empty string"
                )
            agent_card_path = agent_card_path.strip()

        return A2AClientConfiguration(
            streaming=self._boolean(client, "streaming", default=True),
            polling=self._boolean(client, "polling", default=False),
            supported_protocol_bindings=bindings,
            use_client_preference=self._boolean(
                client, "use_client_preference", default=False
            ),
            accepted_output_modes=tuple(
                self._string_list(client, "accepted_output_modes")
            ),
            timeout_seconds=float(timeout),
            agent_card_path=agent_card_path,
            tls=A2AClientTlsConfiguration(
                enabled=tls_enabled,
                trust_bundle=trust_bundle,
                certificate_file=certificate_file,
                private_key_file=private_key_file,
            ),
            credentials=tuple(credentials),
            oauth=oauth,
        )

    @staticmethod
    def _require_table(
        document: dict[str, Any], name: str, *, parent: str | None = None
    ) -> dict[str, Any]:
        value = document.get(name)
        if not isinstance(value, dict):
            location = f"[{parent}.{name}]" if parent else f"[{name}]"
            raise ConfigurationError(f"A2A client configuration requires {location}")
        return value

    @staticmethod
    def _boolean(document: dict[str, Any], name: str, *, default: bool) -> bool:
        value = document.get(name, default)
        if not isinstance(value, bool):
            raise ConfigurationError(f"A2A client {name} must be a boolean")
        return value

    @staticmethod
    def _number(document: dict[str, Any], name: str, *, default: float) -> float:
        value = document.get(name, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigurationError(f"A2A client {name} must be numeric")
        return float(value)

    @staticmethod
    def _string_list(document: dict[str, Any], name: str) -> list[str]:
        value = document.get(name, [])
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            raise ConfigurationError(
                f"A2A client {name} must be a list of non-empty strings"
            )
        return [item.strip() for item in value]

    @staticmethod
    def _destination_path(document: dict[str, Any], name: str, base: Path) -> Path:
        """Resolve an OAuth output path without requiring the file to exist yet."""
        value = document.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(
                f"A2A client OAuth {name} must be a non-empty path"
            )
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = base / path
        path = path.resolve()
        if not path.parent.is_dir():
            raise ConfigurationError(
                f"A2A client OAuth {name} parent directory does not exist",
                details={"path": str(path), "parent": str(path.parent)},
            )
        return path

    @staticmethod
    def _required_path(document: dict[str, Any], name: str, base: Path) -> Path:
        value = document.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(f"A2A client TLS {name} is required")
        return A2AClientConfigurationLoader._resolve_existing_path(value, name, base)

    @staticmethod
    def _optional_path(document: dict[str, Any], name: str, base: Path) -> Path | None:
        value = document.get(name)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(f"A2A client TLS {name} must be a non-empty path")
        return A2AClientConfigurationLoader._resolve_existing_path(value, name, base)

    @staticmethod
    def _resolve_existing_path(value: str, name: str, base: Path) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = base / path
        path = path.resolve()
        if not path.is_file():
            raise ConfigurationError(
                f"A2A client TLS {name} does not exist", details={"path": str(path)}
            )
        return path
