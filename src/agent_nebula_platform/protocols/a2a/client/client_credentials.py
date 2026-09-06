"""Credential providers for official A2A client security schemes."""

from __future__ import annotations

from dataclasses import dataclass

from agent_nebula_platform.platform.errors import AuthenticationError
from agent_nebula_platform.security.oauth.client.models import OAuthTokenRequest
from agent_nebula_platform.security.oauth.client.service import OAuthClientService

from .client_security import A2AClientCredential, A2AClientSecurityRequest


@dataclass(frozen=True, slots=True)
class A2AStaticCredential:
    """Externally provisioned credential bound to one Agent Card scheme name."""

    scheme_name: str
    value: str


class A2AApiKeyCredentialProvider:
    """Apply configured API-key credentials according to the remote Agent Card location."""

    scheme_type = "api_key_security_scheme"

    def __init__(self, credentials: tuple[A2AStaticCredential, ...]) -> None:
        self._credentials = {item.scheme_name: item.value for item in credentials}

    def can_satisfy(self, request: A2AClientSecurityRequest) -> bool:
        return request.scheme_name in self._credentials

    async def acquire(self, request: A2AClientSecurityRequest) -> A2AClientCredential:
        value = self._credentials[request.scheme_name]
        definition = request.scheme.api_key_security_scheme
        if definition.location == "header":
            return A2AClientCredential(headers=((definition.name, value),))
        if definition.location == "query":
            return A2AClientCredential(query_parameters=((definition.name, value),))
        if definition.location == "cookie":
            return A2AClientCredential(cookie_parameters=((definition.name, value),))
        raise AuthenticationError("Unsupported A2A API-key location")


class A2AHttpCredentialProvider:
    """Apply opaque credentials for the HTTP auth scheme declared by the Agent Card."""

    scheme_type = "http_auth_security_scheme"

    def __init__(self, credentials: tuple[A2AStaticCredential, ...]) -> None:
        self._credentials = {item.scheme_name: item.value for item in credentials}

    def can_satisfy(self, request: A2AClientSecurityRequest) -> bool:
        return request.scheme_name in self._credentials

    async def acquire(self, request: A2AClientSecurityRequest) -> A2AClientCredential:
        definition = request.scheme.http_auth_security_scheme
        return A2AClientCredential(
            headers=(
                (
                    "Authorization",
                    f"{definition.scheme} {self._credentials[request.scheme_name]}",
                ),
            )
        )


class A2AOidcCredentialProvider:
    """Apply an externally acquired OIDC bearer token to a matching scheme."""

    scheme_type = "open_id_connect_security_scheme"

    def __init__(self, credentials: tuple[A2AStaticCredential, ...]) -> None:
        self._credentials = {item.scheme_name: item.value for item in credentials}

    def can_satisfy(self, request: A2AClientSecurityRequest) -> bool:
        return request.scheme_name in self._credentials

    async def acquire(self, request: A2AClientSecurityRequest) -> A2AClientCredential:
        return A2AClientCredential(
            headers=(
                ("Authorization", f"Bearer {self._credentials[request.scheme_name]}"),
            )
        )


class A2AMutualTlsCredentialProvider:
    """Mark mTLS requirements satisfiable when Step 4 configured a client TLS identity."""

    scheme_type = "mtls_security_scheme"

    def __init__(self, *, identity_configured: bool) -> None:
        self._identity_configured = identity_configured

    def can_satisfy(self, request: A2AClientSecurityRequest) -> bool:
        del request
        return self._identity_configured

    async def acquire(self, request: A2AClientSecurityRequest) -> A2AClientCredential:
        del request
        if not self._identity_configured:
            raise AuthenticationError(
                "A2A mTLS security requires a configured client certificate"
            )
        return A2AClientCredential(transport_identity=True)


class A2AOAuth2CredentialProvider:
    """Acquire OAuth credentials through Platform's SDK-backed OAuth client service.

    This adapter is intentionally scheme-name agnostic. The remote requirement supplies
    scopes and the selected A2A interface supplies the protected-resource identifier.
    """

    scheme_type = "oauth2_security_scheme"

    def __init__(self, *, service: OAuthClientService, resource: str) -> None:
        self._service = service
        self._resource = resource

    def can_satisfy(self, request: A2AClientSecurityRequest) -> bool:
        definition = request.scheme.oauth2_security_scheme
        flows = definition.flows
        return flows.HasField("client_credentials")

    async def acquire(self, request: A2AClientSecurityRequest) -> A2AClientCredential:
        token = await self._service.token(
            OAuthTokenRequest(resource=self._resource, scopes=request.required_values)
        )
        # Existing Platform OAuth service issues DPoP-bound tokens. A fresh proof is
        # generated by protected_request so htm/htu bind to the actual A2A endpoint.
        protected = await self.acquire_for_request_target(
            request,
            http_method="POST",
            target_uri=self._resource,
        )
        del token
        return protected

    async def acquire_for_request_target(
        self,
        request: A2AClientSecurityRequest,
        *,
        http_method: str,
        target_uri: str,
    ) -> A2AClientCredential:
        """Build OAuth/DPoP headers bound to the actual outbound HTTP request.

        RFC 9449 binds ``htu`` to the HTTP URI where the proof is presented.
        The OAuth resource identifier remains independent and continues to be
        supplied through RFC 8707 token acquisition.
        """

        protected = await self._service.protected_request(
            http_method=http_method,
            target_uri=target_uri,
            resource=self._resource,
            scopes=request.required_values,
        )
        return A2AClientCredential(headers=tuple(protected.headers.items()))


def load_static_credentials(configuration) -> tuple[A2AStaticCredential, ...]:
    """Load configured opaque credentials without exposing secret values in configuration models."""
    credentials: list[A2AStaticCredential] = []
    for item in configuration.credentials:
        try:
            value = item.secret_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise AuthenticationError(
                "Unable to read configured A2A client credential",
                details={"scheme_name": item.scheme_name},
            ) from exc
        if not value:
            raise AuthenticationError(
                "Configured A2A client credential is empty",
                details={"scheme_name": item.scheme_name},
            )
        credentials.append(A2AStaticCredential(item.scheme_name, value))
    return tuple(credentials)
