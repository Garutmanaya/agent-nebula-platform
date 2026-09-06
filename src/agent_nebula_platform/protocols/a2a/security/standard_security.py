"""Adapters from official A2A 1.0 security schemes to generic SDK authenticators."""

from __future__ import annotations

from dataclasses import dataclass

from a2a.types import SecurityScheme
from agent_nebula_sdk.core.errors import AgentNebulaSdkError
from agent_nebula_sdk.security import (
    ApiKeyAuthenticator,
    ApiKeyRequest,
    AuthenticatedIdentity,
    HttpAuthAuthenticator,
    MtlsClientCertificateAuthenticator,
    OidcJwtAuthenticator,
)

from agent_nebula_platform.platform.errors import (
    AuthenticationError,
    ConfigurationError,
)

from .security import A2AAuthenticatedPrincipal, A2ASecurityRequest


def _principal(
    *, scheme_name: str, identity: AuthenticatedIdentity
) -> A2AAuthenticatedPrincipal:
    """Convert an SDK authenticated identity into Runtime's A2A security context."""
    return A2AAuthenticatedPrincipal(
        scheme_name=scheme_name,
        subject=identity.subject,
        attributes=dict(identity.attributes),
    )


class A2AApiKeyAuthenticator:
    """Enforce official APIKeySecurityScheme definitions through SDK verifiers."""

    scheme_type = "api_key_security_scheme"

    def __init__(self, authenticators: dict[str, ApiKeyAuthenticator]) -> None:
        self._authenticators = dict(authenticators)

    def validate_scheme(self, *, scheme_name: str, scheme: SecurityScheme) -> None:
        """Fail startup if an advertised API-key scheme cannot be enforced."""
        definition = scheme.api_key_security_scheme
        if scheme_name not in self._authenticators:
            raise ConfigurationError(
                f"No API-key verifier is configured for A2A scheme {scheme_name!r}"
            )
        if (
            definition.location not in {"header", "query", "cookie"}
            or not definition.name
        ):
            raise ConfigurationError(
                "A2A API-key scheme has an unsupported location or empty name",
                details={"scheme_name": scheme_name},
            )

    def authenticate(
        self,
        *,
        scheme_name: str,
        scheme: SecurityScheme,
        required_values: tuple[str, ...],
        request: A2ASecurityRequest,
    ) -> A2AAuthenticatedPrincipal:
        """Extract and verify the API key according to the official scheme definition."""
        del required_values
        authenticator = self._authenticators.get(scheme_name)
        if authenticator is None:
            raise AuthenticationError(
                f"No API-key verifier is configured for A2A scheme {scheme_name!r}"
            )
        definition = scheme.api_key_security_scheme
        try:
            identity = authenticator.authenticate(
                request=ApiKeyRequest(
                    headers=request.headers,
                    target_uri=request.target_uri,
                ),
                location=definition.location,
                name=definition.name,
            )
        except AgentNebulaSdkError as exc:
            raise AuthenticationError("A2A API-key authentication failed") from exc
        return _principal(scheme_name=scheme_name, identity=identity)


class A2AHttpAuthAuthenticator:
    """Enforce official HTTPAuthSecurityScheme definitions through SDK verifiers."""

    scheme_type = "http_auth_security_scheme"

    def __init__(self, authenticators: dict[str, HttpAuthAuthenticator]) -> None:
        self._authenticators = dict(authenticators)

    def validate_scheme(self, *, scheme_name: str, scheme: SecurityScheme) -> None:
        """Require a verifier matching the HTTP scheme advertised by the Agent Card."""
        authenticator = self._authenticators.get(scheme_name)
        if authenticator is None:
            raise ConfigurationError(
                f"No HTTP-auth verifier is configured for A2A scheme {scheme_name!r}"
            )
        advertised = scheme.http_auth_security_scheme.scheme
        if authenticator.scheme.lower() != advertised.lower():
            raise ConfigurationError(
                "A2A HTTP-auth verifier does not match the advertised scheme",
                details={"scheme_name": scheme_name, "advertised": advertised},
            )

    def authenticate(
        self,
        *,
        scheme_name: str,
        scheme: SecurityScheme,
        required_values: tuple[str, ...],
        request: A2ASecurityRequest,
    ) -> A2AAuthenticatedPrincipal:
        """Verify the Authorization header using the configured HTTP scheme."""
        del required_values
        authenticator = self._authenticators.get(scheme_name)
        if authenticator is None:
            raise AuthenticationError(
                f"No HTTP-auth verifier is configured for A2A scheme {scheme_name!r}"
            )
        advertised = scheme.http_auth_security_scheme.scheme
        if authenticator.scheme.lower() != advertised.lower():
            raise ConfigurationError(
                "A2A HTTP-auth verifier does not match the advertised scheme",
                details={"scheme_name": scheme_name, "advertised": advertised},
            )
        try:
            identity = authenticator.authenticate(
                request.headers.get("authorization", "")
            )
        except AgentNebulaSdkError as exc:
            raise AuthenticationError("A2A HTTP authentication failed") from exc
        return _principal(scheme_name=scheme_name, identity=identity)


@dataclass(frozen=True, slots=True)
class A2AOidcValidationContext:
    """Local OIDC expectations not carried by the A2A Agent Card."""

    authenticator: OidcJwtAuthenticator
    issuer: str
    audiences: tuple[str, ...]
    discovery_url: str


class A2AOpenIdConnectAuthenticator:
    """Validate bearer JWTs for official OpenID Connect security schemes."""

    scheme_type = "open_id_connect_security_scheme"

    def __init__(self, contexts: dict[str, A2AOidcValidationContext]) -> None:
        self._contexts = dict(contexts)

    def validate_scheme(self, *, scheme_name: str, scheme: SecurityScheme) -> None:
        """Require local OIDC policy to match the advertised discovery document."""
        context = self._contexts.get(scheme_name)
        if context is None:
            raise ConfigurationError(
                f"No OIDC validation context is configured for A2A scheme {scheme_name!r}"
            )
        if (
            context.discovery_url
            != scheme.open_id_connect_security_scheme.open_id_connect_url
        ):
            raise ConfigurationError(
                "A2A OIDC validation context does not match advertised discovery URL",
                details={"scheme_name": scheme_name},
            )

    def authenticate(
        self,
        *,
        scheme_name: str,
        scheme: SecurityScheme,
        required_values: tuple[str, ...],
        request: A2ASecurityRequest,
    ) -> A2AAuthenticatedPrincipal:
        """Validate the OIDC bearer JWT against configured issuer and audience policy."""
        del required_values
        context = self._contexts.get(scheme_name)
        if context is None:
            raise AuthenticationError(
                f"No OIDC validation context is configured for A2A scheme {scheme_name!r}"
            )
        if (
            context.discovery_url
            != scheme.open_id_connect_security_scheme.open_id_connect_url
        ):
            raise ConfigurationError(
                "A2A OIDC validation context does not match advertised discovery URL",
                details={"scheme_name": scheme_name},
            )
        authorization = request.headers.get("authorization", "")
        prefix, sep, token = authorization.partition(" ")
        if not sep or prefix.lower() != "bearer" or not token.strip():
            raise AuthenticationError(
                "A2A OpenID Connect request requires Bearer authorization"
            )
        try:
            identity = context.authenticator.authenticate(
                token.strip(),
                issuer=context.issuer,
                audiences=context.audiences,
            )
        except AgentNebulaSdkError as exc:
            raise AuthenticationError(
                "A2A OpenID Connect authentication failed"
            ) from exc
        return _principal(scheme_name=scheme_name, identity=identity)


class A2AMutualTlsAuthenticator:
    """Enforce MutualTlsSecurityScheme using the actual transport peer certificate."""

    scheme_type = "mtls_security_scheme"

    def __init__(self, authenticator: MtlsClientCertificateAuthenticator) -> None:
        self._authenticator = authenticator

    def authenticate(
        self,
        *,
        scheme_name: str,
        scheme: SecurityScheme,
        required_values: tuple[str, ...],
        request: A2ASecurityRequest,
    ) -> A2AAuthenticatedPrincipal:
        """Authenticate the TLS client certificate against configured trust anchors."""
        del scheme, required_values
        certificate = request.peer_certificate
        if not isinstance(certificate, bytes) or not certificate:
            raise AuthenticationError(
                "A2A mTLS request is missing the TLS peer certificate"
            )
        try:
            identity = self._authenticator.authenticate(certificate)
        except AgentNebulaSdkError as exc:
            raise AuthenticationError(
                "A2A mTLS client-certificate authentication failed"
            ) from exc
        return _principal(scheme_name=scheme_name, identity=identity)
