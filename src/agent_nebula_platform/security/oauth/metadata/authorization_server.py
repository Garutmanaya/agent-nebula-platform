"""Verified RFC 8414 Authorization Server metadata resolution for Platform."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from agent_nebula_platform.platform.errors import ConfigurationError, RemoteServiceError


@dataclass(frozen=True, slots=True)
class AuthorizationServerConnection:
    """Transport and optional metadata overrides for one Authorization Server."""

    base_url: str
    metadata_path: str = "/.well-known/oauth-authorization-server"
    issuer: str | None = None
    jwks_uri: str | None = None
    token_endpoint: str | None = None
    registration_endpoint: str | None = None
    timeout_seconds: float = 10.0


@dataclass(frozen=True, slots=True)
class AuthorizationServerMetadata:
    """Authorization Server metadata required by Platform security composition."""

    issuer: str
    jwks_uri: str
    token_endpoint: str | None = None
    registration_endpoint: str | None = None


class AuthorizationServerMetadataResolver:
    """Resolve RFC 8414 metadata over verified HTTPS with explicit overrides."""

    def resolve(
        self,
        *,
        connection: AuthorizationServerConnection,
        trust_bundle_file: str,
    ) -> AuthorizationServerMetadata:
        """Return configured metadata or retrieve the missing values using RFC 8414."""

        if connection.issuer is not None and connection.jwks_uri is not None:
            metadata = AuthorizationServerMetadata(
                issuer=connection.issuer.rstrip("/"),
                jwks_uri=connection.jwks_uri,
                token_endpoint=connection.token_endpoint,
                registration_endpoint=connection.registration_endpoint,
            )
            self._validate_https_metadata(metadata)
            return metadata
        metadata_url = urljoin(
            connection.base_url.rstrip("/") + "/",
            connection.metadata_path.lstrip("/"),
        )
        try:
            with httpx.Client(
                verify=trust_bundle_file,
                timeout=httpx.Timeout(connection.timeout_seconds),
                follow_redirects=False,
            ) as client:
                response = client.get(metadata_url)
        except httpx.HTTPError as exc:
            raise RemoteServiceError(
                f"Unable to retrieve Authorization Server metadata from {metadata_url}"
            ) from exc
        if response.status_code != 200:
            raise RemoteServiceError(
                f"Authorization Server metadata request failed with HTTP {response.status_code}",
                details={"url": metadata_url},
            )
        try:
            document = response.json()
        except ValueError as exc:
            raise RemoteServiceError(
                "Authorization Server metadata response is not valid JSON"
            ) from exc
        if not isinstance(document, dict):
            raise RemoteServiceError(
                "Authorization Server metadata response must be a JSON object"
            )
        issuer = connection.issuer or document.get("issuer")
        jwks_uri = connection.jwks_uri or document.get("jwks_uri")
        if not isinstance(issuer, str) or not issuer.strip():
            raise ConfigurationError("Authorization Server metadata is missing issuer")
        if not isinstance(jwks_uri, str) or not jwks_uri.strip():
            raise ConfigurationError("Authorization Server metadata is missing jwks_uri")
        metadata = AuthorizationServerMetadata(
            issuer=issuer.rstrip("/"),
            jwks_uri=jwks_uri,
            token_endpoint=connection.token_endpoint or document.get("token_endpoint"),
            registration_endpoint=(
                connection.registration_endpoint or document.get("registration_endpoint")
            ),
        )
        self._validate_https_metadata(metadata)
        return metadata

    @staticmethod
    def _validate_https_metadata(metadata: AuthorizationServerMetadata) -> None:
        """Require absolute HTTPS endpoints without embedded credentials/fragments."""

        fields = [("issuer", metadata.issuer), ("jwks_uri", metadata.jwks_uri)]
        if metadata.token_endpoint is not None:
            fields.append(("token_endpoint", metadata.token_endpoint))
        if metadata.registration_endpoint is not None:
            fields.append(("registration_endpoint", metadata.registration_endpoint))
        for field_name, value in fields:
            parsed = urlsplit(value)
            if parsed.scheme.lower() != "https" or not parsed.hostname:
                raise ConfigurationError(
                    f"Authorization Server {field_name} must be an absolute HTTPS URL"
                )
            if parsed.username or parsed.password or parsed.fragment:
                raise ConfigurationError(
                    f"Authorization Server {field_name} contains forbidden URL components"
                )
