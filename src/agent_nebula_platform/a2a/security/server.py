"""Agent Nebula A2A integration.

This module contains only Nebula-specific functionality layered on a2a-sdk.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from a2a.types import AgentCard, SecurityScheme
from agent_nebula_platform.platform.errors import AuthenticationError, ConfigurationError
from a2a.types import SecurityScheme
from agent_nebula_sdk.core.errors import AgentNebulaSdkError
from agent_nebula_sdk.security import ApiKeyAuthenticator, ApiKeyRequest, AuthenticatedIdentity, HttpAuthAuthenticator, MtlsClientCertificateAuthenticator, OidcJwtAuthenticator
from agent_nebula_platform.platform.errors import AuthenticationError
from agent_nebula_platform.security.oauth.protected_resource import ProtectedResourceRequest, ProtectedResourceService
from pathlib import Path
from a2a.types import AgentCard
from agent_nebula_sdk.adapters.httpx_transport import HttpxTransport
from agent_nebula_sdk.oauth.rfc8414 import AuthorizationServerMetadataClient
from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.platform.events import NullEventSink
from agent_nebula_platform.security.oauth.metadata import AuthorizationServerMetadata, ProtectedResourceMetadataFactory, ProtectedResourceMetadataProvider
from agent_nebula_platform.security.oauth.protected_resource.factory import ProtectedResourceRuntime, ProtectedResourceRuntimeFactory
import hmac
import tomllib
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa
from agent_nebula_sdk.core.encoding import encode_base64url
from agent_nebula_sdk.core.errors import ProtocolValidationError
from agent_nebula_sdk.jose.jwk.models import RsaPublicJwk
from agent_nebula_sdk.security import ApiKeyAuthenticator, AuthenticatedIdentity, HttpAuthAuthenticator, MtlsClientCertificateAuthenticator, MtlsTrustPolicy, OidcJwtAuthenticator
from agent_nebula_platform.security.oauth.protected_resource import ProtectedResourceService
from a2a.server.context import ServerCallContext
from a2a.server.routes.common import DefaultServerCallContextBuilder
from starlette.exceptions import HTTPException
from starlette.requests import Request

@dataclass(frozen=True, slots=True)
class A2ASecurityRequest:
    """Transport-neutral security material for one incoming A2A call."""
    headers: dict[str, str]
    http_method: str
    target_uri: str
    peer_certificate: object | None = None

@dataclass(frozen=True, slots=True)
class A2AAuthenticatedPrincipal:
    """Trusted result returned by one configured security authenticator."""
    scheme_name: str
    subject: str
    attributes: dict[str, Any]

class A2ASecuritySchemeAuthenticator(Protocol):
    """Authenticate one concrete official A2A SecurityScheme family."""

    @property
    def scheme_type(self) -> str:
        """Return the official SecurityScheme oneof field handled by this authenticator."""

    def authenticate(self, *, scheme_name: str, scheme: SecurityScheme, required_values: tuple[str, ...], request: A2ASecurityRequest) -> A2AAuthenticatedPrincipal:
        """Authenticate or raise AuthenticationError."""

class A2AServerSecurityService:
    """Evaluate advertised A2A security requirements.

    Card-level requirements can be authenticated as soon as the HTTP request
    enters the a2a-sdk server pipeline. Skill-level requirements are different:
    the selected ``AgentSkill.id`` is carried by the Nebula skill-selection
    extension and is not known until ``RequestContext`` is built. Those
    requirements are therefore authorized later, immediately before dispatch.
    """

    # SECURITY BOUNDARY: credentials are validated exactly once at ingress.
    # The trusted principals produced by that validation are the only input to
    # later AgentSkill authorization.  In particular, a DPoP proof must never
    # be replayed through an authenticator for a second policy check.
    _PRINCIPALS_STATE_KEY = 'agent_nebula.security.principals'
    _REQUEST_STATE_KEY = 'agent_nebula.security.request'

    def __init__(self, *, agent_card: AgentCard, authenticators: tuple[A2ASecuritySchemeAuthenticator, ...]) -> None:
        self._agent_card = agent_card
        self._authenticators = {item.scheme_type: item for item in authenticators}
        if len(self._authenticators) != len(authenticators):
            raise ConfigurationError('A2A security authenticator scheme types must be unique')

    @property
    def required(self) -> bool:
        """Return whether the Agent Card itself requires authentication."""
        return bool(self._agent_card.security_requirements)

    @property
    def has_skill_requirements(self) -> bool:
        """Return whether any advertised skill overrides card-level security."""
        return any(skill.security_requirements for skill in self._agent_card.skills)

    def validate_configuration(self) -> None:
        """Fail startup when any advertised card or skill requirement cannot be enforced.

        A2A permits ``AgentSkill.security_requirements`` to override the Agent
        Card defaults. Validating only ``AgentCard.security_requirements`` would
        allow the server to advertise a protected skill without a corresponding
        authenticator, so both levels must be checked at startup.
        """
        self._validate_requirements(
            self._agent_card.security_requirements,
            owner='AgentCard',
        )
        for skill in self._agent_card.skills:
            self._validate_requirements(
                skill.security_requirements,
                owner=f'AgentSkill {skill.id!r}',
            )

    def authenticate(self, request: A2ASecurityRequest) -> tuple[A2AAuthenticatedPrincipal, ...]:
        """Authenticate and authorize the AgentCard-level requirement.

        NEBULA A2A SECURITY: A2A 1.0 advertises security schemes and
        requirements, but credential validation is supplied by the deployment.
        Nebula deliberately separates credential authentication from requirement
        authorization.  Authenticators validate a scheme once with no policy
        scopes; the requirement evaluator then checks scopes/values against the
        trusted principal.  This is required for DPoP because trying multiple
        policy alternatives must never re-submit the same proof to replay
        detection.
        """
        principals: dict[str, A2AAuthenticatedPrincipal] = {}
        failures: dict[str, AuthenticationError] = {}
        self._satisfy_requirements(
            self._agent_card.security_requirements,
            request=request,
            principals=principals,
            failures=failures,
            owner='AgentCard',
        )
        return tuple(principals.values())

    def authorize_skill(
        self,
        *,
        skill_id: str,
        call_context: ServerCallContext,
    ) -> tuple[A2AAuthenticatedPrincipal, ...]:
        """Authenticate missing schemes once, then authorize the selected skill.

        NEBULA A2A SECURITY IMPLEMENTATION:
        ``AgentCard.securityRequirements`` and
        ``AgentSkill.securityRequirements`` are independent A2A 1.0 policy
        declarations.  A skill may therefore require authentication even when
        the AgentCard itself is public, or may require a different mechanism
        from the AgentCard (for example agent=mTLS, skill=OAuth+API-key).

        Authentication results are cached by advertised scheme name for the
        lifetime of this server call.  Existing results are always reused; only
        a scheme not previously needed by the request may invoke its
        authenticator.  Authorization may run repeatedly, but cryptographic
        credential validation (including DPoP replay processing) runs at most
        once per scheme per request.
        """
        skill = next((item for item in self._agent_card.skills if item.id == skill_id), None)
        if skill is None:
            raise AuthenticationError(f'A2A skill is not advertised by the server: {skill_id}')
        if not skill.security_requirements:
            return ()

        cached = call_context.state.get(self._PRINCIPALS_STATE_KEY, ())
        if not isinstance(cached, tuple):
            raise AuthenticationError('A2A authenticated security context has an invalid shape')
        principals = {principal.scheme_name: principal for principal in cached}
        security_request = call_context.state.get(self._REQUEST_STATE_KEY)
        if security_request is not None and not isinstance(security_request, A2ASecurityRequest):
            raise AuthenticationError('A2A request security context has an invalid shape')

        authorized = self._satisfy_requirements(
            skill.security_requirements,
            request=security_request,
            principals=principals,
            failures={},
            owner=f'AgentSkill {skill.id!r}',
        )
        # Persist every successful authentication, including a principal learned
        # while evaluating an OR alternative that was not ultimately selected.
        # A later policy check must reuse it rather than revalidate credentials.
        call_context.state[self._PRINCIPALS_STATE_KEY] = tuple(principals.values())
        return authorized

    def _satisfy_requirements(
        self,
        requirements,
        *,
        request: A2ASecurityRequest | None,
        principals: dict[str, A2AAuthenticatedPrincipal],
        failures: dict[str, AuthenticationError],
        owner: str,
    ) -> tuple[A2AAuthenticatedPrincipal, ...]:
        """Evaluate A2A OR-of-AND requirements with authenticate-once caching.

        Each SecurityRequirement object is one OR alternative.  Every scheme in
        that object is ANDed.  Scheme authentication is independent of policy
        values/scopes; values are checked only after a trusted principal exists.
        """
        if not requirements:
            return ()
        for requirement in requirements:
            authorized: list[A2AAuthenticatedPrincipal] = []
            satisfied = True
            for scheme_name, values in requirement.schemes.items():
                principal = principals.get(scheme_name)
                if principal is None:
                    if scheme_name in failures:
                        satisfied = False
                        break
                    if request is None:
                        raise AuthenticationError(
                            f'{owner} requires A2A scheme {scheme_name!r}, but request credential context is unavailable'
                        )
                    scheme = self._agent_card.security_schemes[scheme_name]
                    scheme_type = scheme.WhichOneof('scheme')
                    authenticator = self._authenticators.get(scheme_type or '')
                    if authenticator is None:
                        raise AuthenticationError(
                            f'No authenticator is configured for A2A scheme {scheme_name!r}'
                        )
                    try:
                        # AUTHENTICATION ONLY.  Policy scopes are intentionally
                        # empty here.  OAuth/OIDC scope enforcement belongs below
                        # so one DPoP proof cannot be consumed once per alternative.
                        principal = authenticator.authenticate(
                            scheme_name=scheme_name,
                            scheme=scheme,
                            required_values=(),
                            request=request,
                        )
                    except AuthenticationError as exc:
                        failures[scheme_name] = exc
                        satisfied = False
                        break
                    principals[scheme_name] = principal

                required_values = tuple(values.list)
                if required_values and not self._principal_grants_values(principal, required_values):
                    satisfied = False
                    break
                authorized.append(principal)
            if satisfied:
                return tuple(authorized)
        raise AuthenticationError(
            f'A2A request did not satisfy any advertised security requirement for {owner}'
        )

    @staticmethod
    def _principal_grants_values(
        principal: A2AAuthenticatedPrincipal,
        required_values: tuple[str, ...],
    ) -> bool:
        """Evaluate trusted OAuth/OIDC scope values without credential validation."""
        security = principal.attributes.get('security')
        granted = getattr(security, 'granted_scopes', None)
        if granted is None:
            granted = principal.attributes.get('granted_scopes')
        if granted is None:
            granted = principal.attributes.get('scopes')
        if isinstance(granted, str):
            granted_values = set(granted.split())
        elif granted is not None:
            granted_values = set(granted)
        else:
            return False
        return set(required_values).issubset(granted_values)

    def _validate_requirements(self, requirements, *, owner: str) -> None:
        for requirement in requirements:
            for scheme_name in requirement.schemes:
                scheme = self._agent_card.security_schemes.get(scheme_name)
                if scheme is None:
                    raise ConfigurationError(
                        'A2A security requirement references an undefined scheme',
                        details={'owner': owner, 'scheme_name': scheme_name},
                    )
                scheme_type = scheme.WhichOneof('scheme')
                if not scheme_type or scheme_type not in self._authenticators:
                    raise ConfigurationError(
                        'A2A security scheme has no configured server authenticator',
                        details={
                            'owner': owner,
                            'scheme_name': scheme_name,
                            'scheme_type': scheme_type,
                        },
                    )
                authenticator = self._authenticators[scheme_type]
                validate = getattr(authenticator, 'validate_scheme', None)
                if callable(validate):
                    validate(scheme_name=scheme_name, scheme=scheme)


def _principal(*, scheme_name: str, identity: AuthenticatedIdentity) -> A2AAuthenticatedPrincipal:
    """Convert an SDK authenticated identity into Runtime's A2A security context."""
    return A2AAuthenticatedPrincipal(scheme_name=scheme_name, subject=identity.subject, attributes=dict(identity.attributes))

class A2AApiKeyAuthenticator:
    """Enforce official APIKeySecurityScheme definitions through SDK verifiers."""
    scheme_type = 'api_key_security_scheme'

    def __init__(self, authenticators: dict[str, ApiKeyAuthenticator]) -> None:
        self._authenticators = dict(authenticators)

    def validate_scheme(self, *, scheme_name: str, scheme: SecurityScheme) -> None:
        """Fail startup if an advertised API-key scheme cannot be enforced."""
        definition = scheme.api_key_security_scheme
        if scheme_name not in self._authenticators:
            raise ConfigurationError(f'No API-key verifier is configured for A2A scheme {scheme_name!r}')
        if definition.location not in {'header', 'query', 'cookie'} or not definition.name:
            raise ConfigurationError('A2A API-key scheme has an unsupported location or empty name', details={'scheme_name': scheme_name})

    def authenticate(self, *, scheme_name: str, scheme: SecurityScheme, required_values: tuple[str, ...], request: A2ASecurityRequest) -> A2AAuthenticatedPrincipal:
        """Extract and verify the API key according to the official scheme definition."""
        del required_values
        authenticator = self._authenticators.get(scheme_name)
        if authenticator is None:
            raise AuthenticationError(f'No API-key verifier is configured for A2A scheme {scheme_name!r}')
        definition = scheme.api_key_security_scheme
        try:
            identity = authenticator.authenticate(request=ApiKeyRequest(headers=request.headers, target_uri=request.target_uri), location=definition.location, name=definition.name)
        except AgentNebulaSdkError as exc:
            raise AuthenticationError('A2A API-key authentication failed') from exc
        return _principal(scheme_name=scheme_name, identity=identity)

class A2AHttpAuthAuthenticator:
    """Enforce official HTTPAuthSecurityScheme definitions through SDK verifiers."""
    scheme_type = 'http_auth_security_scheme'

    def __init__(self, authenticators: dict[str, HttpAuthAuthenticator]) -> None:
        self._authenticators = dict(authenticators)

    def validate_scheme(self, *, scheme_name: str, scheme: SecurityScheme) -> None:
        """Require a verifier matching the HTTP scheme advertised by the Agent Card."""
        authenticator = self._authenticators.get(scheme_name)
        if authenticator is None:
            raise ConfigurationError(f'No HTTP-auth verifier is configured for A2A scheme {scheme_name!r}')
        advertised = scheme.http_auth_security_scheme.scheme
        if authenticator.scheme.lower() != advertised.lower():
            raise ConfigurationError('A2A HTTP-auth verifier does not match the advertised scheme', details={'scheme_name': scheme_name, 'advertised': advertised})

    def authenticate(self, *, scheme_name: str, scheme: SecurityScheme, required_values: tuple[str, ...], request: A2ASecurityRequest) -> A2AAuthenticatedPrincipal:
        """Verify the Authorization header using the configured HTTP scheme."""
        del required_values
        authenticator = self._authenticators.get(scheme_name)
        if authenticator is None:
            raise AuthenticationError(f'No HTTP-auth verifier is configured for A2A scheme {scheme_name!r}')
        advertised = scheme.http_auth_security_scheme.scheme
        if authenticator.scheme.lower() != advertised.lower():
            raise ConfigurationError('A2A HTTP-auth verifier does not match the advertised scheme', details={'scheme_name': scheme_name, 'advertised': advertised})
        try:
            identity = authenticator.authenticate(request.headers.get('authorization', ''))
        except AgentNebulaSdkError as exc:
            raise AuthenticationError('A2A HTTP authentication failed') from exc
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
    scheme_type = 'open_id_connect_security_scheme'

    def __init__(self, contexts: dict[str, A2AOidcValidationContext]) -> None:
        self._contexts = dict(contexts)

    def validate_scheme(self, *, scheme_name: str, scheme: SecurityScheme) -> None:
        """Require local OIDC policy to match the advertised discovery document."""
        context = self._contexts.get(scheme_name)
        if context is None:
            raise ConfigurationError(f'No OIDC validation context is configured for A2A scheme {scheme_name!r}')
        if context.discovery_url != scheme.open_id_connect_security_scheme.open_id_connect_url:
            raise ConfigurationError('A2A OIDC validation context does not match advertised discovery URL', details={'scheme_name': scheme_name})

    def authenticate(self, *, scheme_name: str, scheme: SecurityScheme, required_values: tuple[str, ...], request: A2ASecurityRequest) -> A2AAuthenticatedPrincipal:
        """Validate the OIDC bearer JWT against configured issuer and audience policy."""
        del required_values
        context = self._contexts.get(scheme_name)
        if context is None:
            raise AuthenticationError(f'No OIDC validation context is configured for A2A scheme {scheme_name!r}')
        if context.discovery_url != scheme.open_id_connect_security_scheme.open_id_connect_url:
            raise ConfigurationError('A2A OIDC validation context does not match advertised discovery URL', details={'scheme_name': scheme_name})
        authorization = request.headers.get('authorization', '')
        prefix, sep, token = authorization.partition(' ')
        if not sep or prefix.lower() != 'bearer' or (not token.strip()):
            raise AuthenticationError('A2A OpenID Connect request requires Bearer authorization')
        try:
            identity = context.authenticator.authenticate(token.strip(), issuer=context.issuer, audiences=context.audiences)
        except AgentNebulaSdkError as exc:
            raise AuthenticationError('A2A OpenID Connect authentication failed') from exc
        return _principal(scheme_name=scheme_name, identity=identity)

class A2AMutualTlsAuthenticator:
    """Enforce MutualTlsSecurityScheme using the actual transport peer certificate."""
    scheme_type = 'mtls_security_scheme'

    def __init__(self, authenticator: MtlsClientCertificateAuthenticator, *, transport_enforced: bool=False) -> None:
        self._authenticator = authenticator
        self._transport_enforced = transport_enforced

    def authenticate(self, *, scheme_name: str, scheme: SecurityScheme, required_values: tuple[str, ...], request: A2ASecurityRequest) -> A2AAuthenticatedPrincipal:
        """Authenticate the TLS client certificate against configured trust anchors."""
        del scheme, required_values
        certificate = request.peer_certificate
        if isinstance(certificate, bytes) and certificate:
            try:
                identity = self._authenticator.authenticate(certificate)
            except AgentNebulaSdkError as exc:
                raise AuthenticationError('A2A mTLS client-certificate authentication failed') from exc
            return _principal(scheme_name=scheme_name, identity=identity)
        if self._transport_enforced:
            return A2AAuthenticatedPrincipal(scheme_name=scheme_name, subject='mtls-transport-client', attributes={'validated_by': 'tls-handshake'})
        raise AuthenticationError('A2A mTLS request is missing the TLS peer certificate')

class A2AOAuth2ProtectedResourceAuthenticator:
    """Validate OAuth2 access tokens with the existing SDK-backed resource server."""
    scheme_type = 'oauth2_security_scheme'

    def __init__(self, service: ProtectedResourceService) -> None:
        self._service = service

    def authenticate(self, *, scheme_name: str, scheme: SecurityScheme, required_values: tuple[str, ...], request: A2ASecurityRequest) -> A2AAuthenticatedPrincipal:
        del scheme
        authorization = request.headers.get('authorization', '')
        expected_prefix = 'DPoP ' if self._service.dpop_required else 'Bearer '
        if not authorization.startswith(expected_prefix):
            token_type = expected_prefix.strip()
            raise AuthenticationError(f'A2A OAuth2 request requires {token_type} authorization')
        access_token = authorization[len(expected_prefix):].strip()
        dpop_proof = request.headers.get('dpop', '').strip() or None
        if not access_token:
            raise AuthenticationError('A2A OAuth2 request is missing an access token')
        if self._service.dpop_required and (not dpop_proof):
            raise AuthenticationError('A2A OAuth2 request is missing a DPoP proof')
        context = self._service.authenticate(ProtectedResourceRequest(access_token=access_token, dpop_proof=dpop_proof, http_method=request.http_method, target_uri=request.target_uri, required_scopes=required_values))
        return A2AAuthenticatedPrincipal(scheme_name=scheme_name, subject=context.subject, attributes={'client_id': context.client_id, 'security': context})

@dataclass(frozen=True, slots=True)
class A2AProtectedResourceComposition:
    """Own OAuth runtime security and its authoritative RFC 9728 metadata.

    The runtime validates inbound OAuth/DPoP requests. ``metadata`` is the same
    protected-resource description used for discovery and Agent Nebula
    onboarding. Keeping both in one composition prevents registration metadata
    from drifting from the resource identifier and authorization server that
    actually protect the A2A endpoint.
    """
    runtime: ProtectedResourceRuntime
    metadata: ProtectedResourceMetadataProvider

class A2AProtectedResourceFactory:
    """Create OAuth validation only when an Agent Card advertises OAuth 2.0."""

    def create(self, *, agent_card: AgentCard, trust_bundle_file: Path | None, timeout_seconds: float=10.0) -> A2AProtectedResourceComposition | None:
        """Resolve RFC 8414 metadata and compose the generic OAuth resource service."""
        metadata_urls = self._oauth_metadata_urls(agent_card)
        if not metadata_urls:
            return None
        if trust_bundle_file is None:
            raise ConfigurationError('OAuth-protected A2A server requires [server.tls].trust_bundle in a2aserver.conf')
        if len(metadata_urls) != 1:
            raise ConfigurationError('A2A OAuth security schemes must advertise one common Authorization Server metadata URL')
        transport = HttpxTransport(timeout_seconds=timeout_seconds, verify=str(trust_bundle_file))
        try:
            metadata = AuthorizationServerMetadataClient(transport=transport).fetch_url(next(iter(metadata_urls)))
        finally:
            transport.close()
        if metadata.jwks_uri is None:
            raise ConfigurationError('Authorization Server metadata for A2A OAuth protection is missing jwks_uri')
        resource = str(agent_card.supported_interfaces[0].url).rstrip('/')
        protected = ProtectedResourceRuntimeFactory().build(resource=resource, issuer=metadata.issuer, jwks_uri=metadata.jwks_uri, ca_file=str(trust_bundle_file), access_token_algorithms=('RS256',), dpop_algorithms=('ES256',), events=NullEventSink(), timeout_seconds=timeout_seconds)
        protected_resource_metadata = ProtectedResourceMetadataFactory().create(resource=resource, resource_name=agent_card.name, authorization_server=AuthorizationServerMetadata(issuer=metadata.issuer, jwks_uri=metadata.jwks_uri, token_endpoint=metadata.token_endpoint, registration_endpoint=metadata.registration_endpoint), scopes=self._oauth_scopes(agent_card), dpop_algorithms=('ES256',))
        return A2AProtectedResourceComposition(runtime=protected, metadata=protected_resource_metadata)

    @staticmethod
    def _oauth_scopes(agent_card: AgentCard) -> tuple[str, ...]:
        """Return OAuth scopes advertised by official A2A 1.0 security schemes.

        Scope identifiers remain owned by the Agent Card.  Platform only
        projects those standard OAuth flow values into RFC 9728 metadata; it
        does not add fields to the A2A Agent Card or reinterpret A2A skills.
        """
        scopes: list[str] = []
        for scheme in agent_card.security_schemes.values():
            if scheme.WhichOneof('scheme') != 'oauth2_security_scheme':
                continue
            flows = scheme.oauth2_security_scheme.flows
            for _, flow in flows.ListFields():
                for scope in flow.scopes:
                    if scope not in scopes:
                        scopes.append(scope)
        return tuple(scopes)

    @staticmethod
    def _oauth_metadata_urls(agent_card: AgentCard) -> set[str]:
        """Return OAuth metadata URLs advertised by official A2A security schemes."""
        urls: set[str] = set()
        for scheme in agent_card.security_schemes.values():
            if scheme.WhichOneof('scheme') != 'oauth2_security_scheme':
                continue
            metadata_url = scheme.oauth2_security_scheme.oauth2_metadata_url
            if not metadata_url:
                raise ConfigurationError('A2A OAuth2 security scheme requires oauth2_metadata_url for server validation')
            urls.add(metadata_url)
        return urls

@dataclass(frozen=True, slots=True)
class _StaticVerifier:
    expected: str
    subject: str

    def verify(self, credential: str) -> AuthenticatedIdentity:
        if not hmac.compare_digest(credential, self.expected):
            raise ProtocolValidationError('credential validation failed', code='invalid_credential')
        return AuthenticatedIdentity(subject=self.subject, attributes={})

@dataclass(frozen=True, slots=True)
class _StaticOidcKeyResolver:
    key: RsaPublicJwk
    issuer: str

    def resolve(self, *, issuer: str, key_id: str, algorithm: str):
        if issuer != self.issuer or key_id != self.key.kid or algorithm != self.key.alg:
            raise ProtocolValidationError('OIDC signing key is not trusted', code='invalid_oidc_key')
        return self.key

class A2AConfiguredSecurityLoader:
    """Build Platform A2A security adapters from private local server configuration.

    AGENT NEBULA SECURITY: ``[security]`` is deliberately outside ``[agent_card]``.
    AgentCard security metadata is public A2A contract data; verifier secrets and
    trust policy are local implementation details and must never be published.
    """

    def load(self, path: Path, *, mtls_transport_enforced: bool=False) -> tuple[object, ...]:
        try:
            with path.open('rb') as stream:
                document = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigurationError(f'Invalid A2A server configuration: {path}') from exc
        security = document.get('security', {})
        if not isinstance(security, dict):
            raise ConfigurationError('a2aserver.conf [security] must be a table')
        root = path.resolve().parent
        result = []
        api = {}
        for name, cfg in self._named(security, 'api_key').items():
            api[name] = ApiKeyAuthenticator(_StaticVerifier(self._secret(cfg, root), self._subject(cfg)))
        if api:
            result.append(A2AApiKeyAuthenticator(api))
        http = {}
        for name, cfg in self._named(security, 'http_auth').items():
            scheme = self._string(cfg, 'scheme')
            http[name] = HttpAuthAuthenticator(scheme=scheme, verifier=_StaticVerifier(self._secret(cfg, root), self._subject(cfg)))
        if http:
            result.append(A2AHttpAuthAuthenticator(http))
        oidc = {}
        for name, cfg in self._named(security, 'oidc').items():
            issuer = self._string(cfg, 'issuer')
            discovery = self._string(cfg, 'discovery_url')
            audiences = tuple(self._strings(cfg, 'audiences'))
            if not audiences:
                raise ConfigurationError('OIDC audiences must not be empty')
            cert = self._path(cfg, 'verification_certificate_file', root)
            kid = self._string(cfg, 'key_id')
            algorithm = self._string(cfg, 'algorithm')
            certificate = x509.load_pem_x509_certificate(cert.read_bytes())
            public = certificate.public_key()
            if not isinstance(public, rsa.RSAPublicKey):
                raise ConfigurationError('Configured OIDC verification certificate must contain an RSA public key')
            numbers = public.public_numbers()
            jwk = RsaPublicJwk(kty='RSA', kid=kid, use='sig', alg=algorithm, n=self._uint(numbers.n), e=self._uint(numbers.e))
            authenticator = OidcJwtAuthenticator(key_resolver=_StaticOidcKeyResolver(jwk, issuer), allowed_algorithms=(algorithm,))
            oidc[name] = A2AOidcValidationContext(authenticator=authenticator, issuer=issuer, audiences=audiences, discovery_url=discovery)
        if oidc:
            result.append(A2AOpenIdConnectAuthenticator(oidc))
        mtls = security.get('mtls')
        if mtls is not None:
            if not isinstance(mtls, dict):
                raise ConfigurationError('[security.mtls] must be a table')
            trust = self._path(mtls, 'trust_bundle', root)
            policy = MtlsTrustPolicy.from_pem(trust_bundle_pem=trust.read_bytes())
            result.append(A2AMutualTlsAuthenticator(MtlsClientCertificateAuthenticator(policy), transport_enforced=mtls_transport_enforced))
        return tuple(result)

    @staticmethod
    def _uint(value: int) -> str:
        return encode_base64url(value.to_bytes((value.bit_length() + 7) // 8, 'big'))

    @staticmethod
    def _named(doc, name):
        value = doc.get(name, {})
        if not isinstance(value, dict):
            raise ConfigurationError(f'[security.{name}] must be a table')
        for k, v in value.items():
            if not isinstance(v, dict):
                raise ConfigurationError(f'[security.{name}.{k}] must be a table')
        return value

    @staticmethod
    def _string(doc, name):
        value = doc.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(f'security {name} must be a non-empty string')
        return value.strip()

    @classmethod
    def _strings(cls, doc, name):
        value = doc.get(name)
        if not isinstance(value, list) or any((not isinstance(x, str) or not x.strip() for x in value)):
            raise ConfigurationError(f'security {name} must be a string list')
        return [x.strip() for x in value]

    @classmethod
    def _path(cls, doc, name, root):
        value = Path(cls._string(doc, name)).expanduser()
        value = value if value.is_absolute() else root / value
        value = value.resolve()
        if not value.is_file():
            raise ConfigurationError(f'security file does not exist: {value}')
        return value

    @classmethod
    def _secret(cls, doc, root):
        value = cls._path(doc, 'secret_file', root).read_text(encoding='utf-8').strip()
        if not value:
            raise ConfigurationError('security credential file is empty')
        return value

    @staticmethod
    def _subject(doc):
        value = doc.get('subject', 'a2a-client')
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError('security subject must be non-empty')
        return value.strip()

@dataclass(frozen=True, slots=True)
class A2AServerSecurityComposition:
    """Security resources composed for one official A2A Agent Card."""
    service: A2AServerSecurityService
    protected_resource: A2AProtectedResourceComposition | None = None

class A2AServerSecurityFactory:
    """Compose all server-side A2A authentication through one boundary.

    AGENT NEBULA SECURITY: A2A defines the advertised security schemes and
    requirement semantics, while Agent Nebula supplies credential validation.
    This factory is the single Platform composition point that joins those two
    responsibilities. Scheme-specific validators remain pluggable adapters;
    OAuth protected-resource construction remains delegated to its existing
    RFC 8414/RFC 9728 implementation.
    """

    def __init__(self, *, protected_resource_factory: A2AProtectedResourceFactory | None=None) -> None:
        self._protected_resource_factory = protected_resource_factory or A2AProtectedResourceFactory()

    def create(self, *, agent_card: AgentCard, trust_bundle_file: Path | None, authenticators: tuple[A2ASecuritySchemeAuthenticator, ...]=(), protected_resource_service: ProtectedResourceService | None=None) -> A2AServerSecurityComposition:
        """Build the security service and any OAuth-owned lifecycle resources.

        ``authenticators`` is the extension seam for API-key, HTTP-auth, OIDC,
        and mTLS validators. Step 1 centralizes composition without changing
        existing application configuration; subsequent examples can supply
        those validators through configuration-driven Platform adapters.
        """
        protected_resource = None
        if protected_resource_service is None:
            protected_resource = self._protected_resource_factory.create(agent_card=agent_card, trust_bundle_file=trust_bundle_file)
            if protected_resource is not None:
                protected_resource_service = protected_resource.runtime.service
        configured = list(authenticators)
        configured_types = {item.scheme_type for item in configured}
        if protected_resource_service is not None and 'oauth2_security_scheme' not in configured_types:
            configured.append(A2AOAuth2ProtectedResourceAuthenticator(protected_resource_service))
        service = A2AServerSecurityService(agent_card=agent_card, authenticators=tuple(configured))
        service.validate_configuration()
        return A2AServerSecurityComposition(service=service, protected_resource=protected_resource)

class A2ASecurityServerCallContextBuilder(DefaultServerCallContextBuilder):
    """Authenticate A2A HTTP calls while preserving the SDK server pipeline.

    AGENT NEBULA SECURITY: A2A advertises security requirements but does not
    implement the credential validation used by Agent Nebula.  This builder
    plugs Nebula's configured authenticators into the official a2a-sdk
    ``ServerCallContextBuilder`` extension point.  Route creation, request
    parsing, task handling, streaming, and dispatch remain owned by a2a-sdk.
    """
    def __init__(self, security: A2AServerSecurityService) -> None:
        self._security = security

    def build(self, request: Request) -> ServerCallContext:
        """Build the SDK context and authenticate requirements known at HTTP ingress.

        Card-level security is known before A2A payload dispatch and is enforced
        here.  Credential validation happens exactly once at this boundary.  The
        resulting trusted principals are stored in ``ServerCallContext.state`` so
        the later RequestHandler can evaluate skill policy without touching the
        access token, DPoP proof, replay cache, or other credential material.
        """
        context = super().build(request)
        security_request = A2ASecurityRequest(
            headers={key.lower(): value for key, value in request.headers.items()},
            http_method=request.method,
            target_uri=str(request.url),
        )
        # NEBULA A2A SECURITY: retain normalized credential material only for the
        # lifetime of this ServerCallContext.  A2A permits skill-only security,
        # so the required scheme may not be known until RequestHandler resolves
        # AgentSkill.securityRequirements.  This state must never be logged or
        # persisted.  Authentication results are cached separately as principals.
        context.state[self._security._REQUEST_STATE_KEY] = security_request
        context.state[self._security._PRINCIPALS_STATE_KEY] = ()
        if not self._security.required:
            return context
        try:
            principals = self._security.authenticate(security_request)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        context.state[self._security._PRINCIPALS_STATE_KEY] = principals
        return context
