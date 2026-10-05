"""Agent Nebula A2A integration.

This module contains only Nebula-specific functionality layered on a2a-sdk.
"""

from __future__ import annotations

from ..config.client import A2AClientOAuthConfiguration, A2AClientTlsConfiguration

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit
from a2a.client.client import ClientCallContext
from a2a.client.interceptors import AfterArgs, BeforeArgs, ClientCallInterceptor
from a2a.client.service_parameters import ServiceParameters
from a2a.types import AgentCard, SecurityScheme
from agent_nebula_platform.platform.errors import AuthenticationError, ConfigurationError
from agent_nebula_platform.platform.errors import AuthenticationError
from agent_nebula_platform.security.oauth.client.models import OAuthTokenRequest
from agent_nebula_platform.security.oauth.client.service import OAuthClientService
import asyncio
from pathlib import Path
import httpx
from agent_nebula_sdk.adapters.httpx_transport import HttpxTransport
from agent_nebula_sdk.jose.jwks.models import JwkSet
from agent_nebula_sdk.oauth.client import OAuthClientFacade
from agent_nebula_sdk.oauth.rfc7523 import ClientAssertionBuilder, Rfc7523Policy
from agent_nebula_sdk.oauth.rfc7591 import ClientMetadata, DynamicClientRegistrationClient
from agent_nebula_sdk.oauth.rfc8414 import AuthorizationServerMetadataClient
from agent_nebula_sdk.oauth.rfc8707 import ResourceParameterCodec
from agent_nebula_sdk.oauth.rfc9449 import DpopProofBuilder, DpopTargetUriNormalizer, Rfc9449Policy
from agent_nebula_sdk.ports.clock import SystemClock
from agent_nebula_platform.platform.events import NullEventSink
from agent_nebula_platform.platform.state import MemoryStateStore
from agent_nebula_platform.security.oauth.client import HttpxOAuthTokenTransport, MemoryOAuthTokenCache, OAuthClientService, OnboardingOAuthClientIdentity

@dataclass(frozen=True, slots=True)
class A2AClientSecurityRequest:
    """Describe one credential request derived from a remote Agent Card."""
    scheme_name: str
    scheme: SecurityScheme
    required_values: tuple[str, ...]
    agent_card: AgentCard
    method: str

@dataclass(frozen=True, slots=True)
class A2AClientCredential:
    """Transport-neutral credential material produced by one provider."""
    headers: tuple[tuple[str, str], ...] = ()
    query_parameters: tuple[tuple[str, str], ...] = ()
    cookie_parameters: tuple[tuple[str, str], ...] = ()
    transport_identity: bool = False

class A2AClientCredentialProvider(Protocol):
    """Acquire credentials for one official A2A security-scheme family."""
    scheme_type: str

    def can_satisfy(self, request: A2AClientSecurityRequest) -> bool:
        """Return whether local credentials can satisfy this exact scheme."""
        ...

    async def acquire(self, request: A2AClientSecurityRequest) -> A2AClientCredential:
        """Acquire fresh or cached credential material for one request."""
        ...

@dataclass(frozen=True, slots=True)
class A2AResolvedSecurityRequirement:
    """Represent one satisfiable AND-group selected from Agent Card OR choices."""
    schemes: tuple[A2AClientSecurityRequest, ...]

class A2AClientSecurityResolver:
    """Resolve Agent Card OR-of-AND security requirements without name conventions."""

    def __init__(self, providers: tuple[A2AClientCredentialProvider, ...]) -> None:
        self._providers = providers

    def resolve(self, *, agent_card: AgentCard, method: str, skill_id: str | None=None) -> A2AResolvedSecurityRequirement:
        """Select the first satisfiable card- or skill-level security requirement.

        NEBULA A2A EXTENSION: when the client has explicitly selected an
        advertised skill, that skill's security requirements take precedence.
        This lets credential providers request least-privilege skill scopes
        before the A2A message is sent. If the skill does not override security,
        normal Agent Card requirements remain authoritative.
        """
        requirements = tuple(agent_card.security_requirements)
        if skill_id is not None:
            skill = next((item for item in agent_card.skills if item.id == skill_id), None)
            if skill is None:
                raise ConfigurationError(f'A2A skill is not advertised by the remote agent: {skill_id}')
            if skill.security_requirements:
                requirements = tuple(skill.security_requirements)
        if not requirements:
            return A2AResolvedSecurityRequirement(())
        schemes = agent_card.security_schemes
        failures: list[str] = []
        for requirement in requirements:
            resolved: list[A2AClientSecurityRequest] = []
            satisfiable = True
            for scheme_name, values in requirement.schemes.items():
                if scheme_name not in schemes:
                    raise ConfigurationError('A2A Agent Card security requirement references an undefined scheme', details={'scheme_name': scheme_name})
                scheme = schemes[scheme_name]
                request = A2AClientSecurityRequest(scheme_name=scheme_name, scheme=scheme, required_values=tuple(values.list), agent_card=agent_card, method=method)
                if self._provider_for(request) is None:
                    failures.append(scheme_name)
                    satisfiable = False
                    break
                resolved.append(request)
            if satisfiable:
                return A2AResolvedSecurityRequirement(tuple(resolved))
        raise AuthenticationError('No advertised A2A security requirement can be satisfied by configured credentials', details={'unavailable_schemes': sorted(set(failures))})

    def provider_for(self, request: A2AClientSecurityRequest) -> A2AClientCredentialProvider:
        """Return the provider selected by official SecurityScheme oneof type."""
        provider = self._provider_for(request)
        if provider is None:
            raise AuthenticationError(f'No credential provider can satisfy A2A scheme {request.scheme_name!r}')
        return provider

    async def close(self) -> None:
        """Close resources owned by configured credential providers."""
        for provider in self._providers:
            close = getattr(provider, 'close', None)
            if close is None:
                continue
            result = close()
            if hasattr(result, '__await__'):
                await result

    def _provider_for(self, request: A2AClientSecurityRequest) -> A2AClientCredentialProvider | None:
        scheme_type = request.scheme.WhichOneof('scheme')
        for provider in self._providers:
            if provider.scheme_type == scheme_type and provider.can_satisfy(request):
                return provider
        return None

class A2AClientSecurityInterceptor(ClientCallInterceptor):
    """Apply Agent Nebula credentials through the official SDK interceptor API.

    AGENT NEBULA SECURITY:
    A2A advertises security requirements but credential acquisition is external
    to the protocol. Agent Nebula implements that acquisition here and injects
    credentials through ``ClientCallInterceptor`` without replacing SDK calls.
    """

    def __init__(self, resolver: A2AClientSecurityResolver) -> None:
        self._resolver = resolver

    async def before(self, args: BeforeArgs) -> None:
        """Resolve OR-of-AND requirements and merge every credential in the selected AND-group."""
        skill_id = None
        if args.context is not None:
            value = args.context.state.get('agent_nebula.a2a.skill_id')
            if isinstance(value, str):
                skill_id = value
        resolved = self._resolver.resolve(agent_card=args.agent_card, method=args.method, skill_id=skill_id)
        if not resolved.schemes:
            return
        context = args.context or ClientCallContext()
        parameters = ServiceParameters()
        if context.service_parameters:
            parameters.update(context.service_parameters)
        for request in resolved.schemes:
            credential = await self._resolver.provider_for(request).acquire(request)
            if credential.query_parameters or credential.cookie_parameters:
                raise ConfigurationError('The official A2A 1.0 client interceptor surface cannot safely apply query/cookie credentials', details={'scheme_name': request.scheme_name})
            for name, value in credential.headers:
                existing = parameters.get(name)
                if existing is not None and existing != value:
                    raise AuthenticationError('A2A compound security requirements produced conflicting headers', details={'header': name})
                parameters[name] = value
        context.service_parameters = parameters
        args.context = context

    async def apply_http_request_security(self, *, agent_card: AgentCard, http_method: str, target_uri: str, headers, skill_id: str | None=None) -> None:
        """Refresh request-bound credentials using the final HTTP method and URI.

        The official A2A interceptor runs before the transport has constructed
        its concrete HTTP request. RFC 9449 DPoP therefore needs this final
        transport hook so ``htm`` and ``htu`` describe the request that actually
        carries the proof. Other credentials remain unchanged.
        """
        resolved = self._resolver.resolve(agent_card=agent_card, method='http_request', skill_id=skill_id)
        normalized_target = _dpop_target_uri(target_uri)
        for security_request in resolved.schemes:
            provider = self._resolver.provider_for(security_request)
            acquire_for_target = getattr(provider, 'acquire_for_request_target', None)
            if acquire_for_target is None:
                continue
            credential = await acquire_for_target(security_request, http_method=http_method, target_uri=normalized_target)
            for name, value in credential.headers:
                headers[name] = value

    async def after(self, args: AfterArgs) -> None:
        """Leave response processing to the official A2A client."""
        del args

    async def close(self) -> None:
        """Close resources owned by credential providers, when present."""
        await self._resolver.close()

def _dpop_target_uri(target_uri: str) -> str:
    """Return the RFC 9449 ``htu`` form: absolute URI without query or fragment."""
    parsed = urlsplit(target_uri)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))

@dataclass(frozen=True, slots=True)
class A2AStaticCredential:
    """Externally provisioned credential bound to one Agent Card scheme name."""
    scheme_name: str
    value: str

class A2AApiKeyCredentialProvider:
    """Apply configured API-key credentials according to the remote Agent Card location."""
    scheme_type = 'api_key_security_scheme'

    def __init__(self, credentials: tuple[A2AStaticCredential, ...]) -> None:
        self._credentials = {item.scheme_name: item.value for item in credentials}

    def can_satisfy(self, request: A2AClientSecurityRequest) -> bool:
        return request.scheme_name in self._credentials

    async def acquire(self, request: A2AClientSecurityRequest) -> A2AClientCredential:
        value = self._credentials[request.scheme_name]
        definition = request.scheme.api_key_security_scheme
        if definition.location == 'header':
            return A2AClientCredential(headers=((definition.name, value),))
        if definition.location == 'query':
            return A2AClientCredential(query_parameters=((definition.name, value),))
        if definition.location == 'cookie':
            return A2AClientCredential(cookie_parameters=((definition.name, value),))
        raise AuthenticationError('Unsupported A2A API-key location')

class A2AHttpCredentialProvider:
    """Apply opaque credentials for the HTTP auth scheme declared by the Agent Card."""
    scheme_type = 'http_auth_security_scheme'

    def __init__(self, credentials: tuple[A2AStaticCredential, ...]) -> None:
        self._credentials = {item.scheme_name: item.value for item in credentials}

    def can_satisfy(self, request: A2AClientSecurityRequest) -> bool:
        return request.scheme_name in self._credentials

    async def acquire(self, request: A2AClientSecurityRequest) -> A2AClientCredential:
        definition = request.scheme.http_auth_security_scheme
        return A2AClientCredential(headers=(('Authorization', f'{definition.scheme} {self._credentials[request.scheme_name]}'),))

class A2AOidcCredentialProvider:
    """Apply an externally acquired OIDC bearer token to a matching scheme."""
    scheme_type = 'open_id_connect_security_scheme'

    def __init__(self, credentials: tuple[A2AStaticCredential, ...]) -> None:
        self._credentials = {item.scheme_name: item.value for item in credentials}

    def can_satisfy(self, request: A2AClientSecurityRequest) -> bool:
        return request.scheme_name in self._credentials

    async def acquire(self, request: A2AClientSecurityRequest) -> A2AClientCredential:
        return A2AClientCredential(headers=(('Authorization', f'Bearer {self._credentials[request.scheme_name]}'),))

class A2AMutualTlsCredentialProvider:
    """Mark mTLS requirements satisfiable when Step 4 configured a client TLS identity."""
    scheme_type = 'mtls_security_scheme'

    def __init__(self, *, identity_configured: bool) -> None:
        self._identity_configured = identity_configured

    def can_satisfy(self, request: A2AClientSecurityRequest) -> bool:
        del request
        return self._identity_configured

    async def acquire(self, request: A2AClientSecurityRequest) -> A2AClientCredential:
        del request
        if not self._identity_configured:
            raise AuthenticationError('A2A mTLS security requires a configured client certificate')
        return A2AClientCredential(transport_identity=True)

class A2AOAuth2CredentialProvider:
    """Acquire OAuth credentials through Platform's SDK-backed OAuth client service.

    This adapter is intentionally scheme-name agnostic. The remote requirement supplies
    scopes and the selected A2A interface supplies the protected-resource identifier.
    """
    scheme_type = 'oauth2_security_scheme'

    def __init__(self, *, service: OAuthClientService, resource: str) -> None:
        self._service = service
        self._resource = resource

    def can_satisfy(self, request: A2AClientSecurityRequest) -> bool:
        definition = request.scheme.oauth2_security_scheme
        flows = definition.flows
        return flows.HasField('client_credentials')

    async def acquire(self, request: A2AClientSecurityRequest) -> A2AClientCredential:
        token = await self._service.token(OAuthTokenRequest(resource=self._resource, scopes=request.required_values))
        protected = await self.acquire_for_request_target(request, http_method='POST', target_uri=self._resource)
        del token
        return protected

    async def acquire_for_request_target(self, request: A2AClientSecurityRequest, *, http_method: str, target_uri: str) -> A2AClientCredential:
        """Build OAuth/DPoP headers bound to the actual outbound HTTP request.

        RFC 9449 binds ``htu`` to the HTTP URI where the proof is presented.
        The OAuth resource identifier remains independent and continues to be
        supplied through RFC 8707 token acquisition.
        """
        protected = await self._service.protected_request(http_method=http_method, target_uri=target_uri, resource=self._resource, scopes=request.required_values)
        return A2AClientCredential(headers=tuple(protected.headers.items()))

def load_static_credentials(configuration) -> tuple[A2AStaticCredential, ...]:
    """Load configured opaque credentials without exposing secret values in configuration models."""
    credentials: list[A2AStaticCredential] = []
    for item in configuration.credentials:
        try:
            value = item.secret_file.read_text(encoding='utf-8').strip()
        except OSError as exc:
            raise AuthenticationError('Unable to read configured A2A client credential', details={'scheme_name': item.scheme_name}) from exc
        if not value:
            raise AuthenticationError('Configured A2A client credential is empty', details={'scheme_name': item.scheme_name})
        credentials.append(A2AStaticCredential(item.scheme_name, value))
    return tuple(credentials)

class A2ADiscoveredOAuth2CredentialProvider:
    """Acquire OAuth credentials and lazily register an unprovisioned A2A caller."""
    scheme_type = 'oauth2_security_scheme'

    def __init__(self, *, configuration: A2AClientOAuthConfiguration, tls: A2AClientTlsConfiguration, timeout_seconds: float) -> None:
        self._configuration = configuration
        self._tls = tls
        self._timeout_seconds = timeout_seconds
        self._services: dict[str, tuple[OAuthClientService, httpx.AsyncClient]] = {}
        self._registration_lock = asyncio.Lock()

    def can_satisfy(self, request: A2AClientSecurityRequest) -> bool:
        return request.scheme.oauth2_security_scheme.flows.HasField('client_credentials')

    async def acquire(self, request: A2AClientSecurityRequest) -> A2AClientCredential:
        resource = self._resource(request)
        return await self.acquire_for_request_target(request, http_method='POST', target_uri=resource)

    async def acquire_for_request_target(self, request: A2AClientSecurityRequest, *, http_method: str, target_uri: str) -> A2AClientCredential:
        definition = request.scheme.oauth2_security_scheme
        if not definition.flows.HasField('client_credentials'):
            raise AuthenticationError('A2A OAuth2 scheme does not advertise client credentials')
        token_endpoint = definition.flows.client_credentials.token_url
        if not token_endpoint:
            raise ConfigurationError('A2A OAuth2 client-credentials flow is missing token_url')
        await self._ensure_client_registration(request)
        protected = await self._service(token_endpoint).protected_request(http_method=http_method, target_uri=target_uri, resource=self._resource(request), scopes=request.required_values)
        return A2AClientCredential(headers=tuple(protected.headers.items()))

    async def close(self) -> None:
        clients = tuple((client for _, client in self._services.values()))
        self._services.clear()
        for client in clients:
            await client.aclose()

    async def _ensure_client_registration(self, request: A2AClientSecurityRequest) -> None:
        if self._read_client_id() is not None:
            return
        async with self._registration_lock:
            if self._read_client_id() is not None:
                return
            metadata_url = request.scheme.oauth2_security_scheme.oauth2_metadata_url
            if not metadata_url:
                raise ConfigurationError('A2A OAuth2 client registration requires oauth2_metadata_url when client_id is absent')
            client_id = await asyncio.to_thread(self._register_client, metadata_url)
            self._write_client_id(client_id)

    def _register_client(self, metadata_url: str) -> str:
        """Use A2A-advertised RFC 8414 metadata to perform standard RFC 7591 DCR."""
        verify: str | bool = str(self._tls.trust_bundle) if self._tls.trust_bundle else True
        transport = HttpxTransport(verify=verify, timeout_seconds=self._timeout_seconds)
        try:
            server = AuthorizationServerMetadataClient(transport=transport).fetch_url(metadata_url)
            if not server.registration_endpoint:
                raise ConfigurationError('A2A OAuth Authorization Server metadata has no registration_endpoint')
            identity = self._identity()
            metadata = ClientMetadata(client_name='Agent Nebula A2A Client', grant_types=('client_credentials',), response_types=(), token_endpoint_auth_method='private_key_jwt', jwks=JwkSet.model_validate(identity.public_jwks_document()))
            response = DynamicClientRegistrationClient(endpoint=server.registration_endpoint, transport=transport).register(metadata)
            return response.client_id
        finally:
            transport.close()

    def _service(self, token_endpoint: str) -> OAuthClientService:
        cached = self._services.get(token_endpoint)
        if cached is not None:
            return cached[0]
        algorithm = self._configuration.algorithm
        identity = self._identity()
        verify: str | bool = str(self._tls.trust_bundle) if self._tls.trust_bundle else True
        client = httpx.AsyncClient(verify=verify, timeout=self._timeout_seconds)
        clock = SystemClock()
        dpop_policy = Rfc9449Policy(allowed_algorithms=frozenset({algorithm}))
        facade = OAuthClientFacade(assertion_builder=ClientAssertionBuilder(clock=clock, policy=Rfc7523Policy(allowed_algorithms=frozenset({algorithm}))), resource_codec=ResourceParameterCodec(), dpop_builder=DpopProofBuilder(clock=clock, policy=dpop_policy, uri_normalizer=DpopTargetUriNormalizer(policy=dpop_policy)))
        service = OAuthClientService(token_endpoint=token_endpoint, facade=facade, identity=identity, transport=HttpxOAuthTokenTransport(client), cache=MemoryOAuthTokenCache(), events=NullEventSink())
        self._services[token_endpoint] = (service, client)
        return service

    def _identity(self) -> OnboardingOAuthClientIdentity:
        return OnboardingOAuthClientIdentity(state_store=MemoryStateStore(), onboarding_state_key='a2a-direct-oauth-client', client_id_file=self._configuration.client_id_file, authentication_key_file=self._configuration.authentication_private_key_file, dpop_key_file=self._configuration.dpop_private_key_file, key_id=self._configuration.key_id, algorithm=self._configuration.algorithm)

    def _read_client_id(self) -> str | None:
        path = self._configuration.client_id_file
        if not path.is_file():
            return None
        return path.read_text(encoding='utf-8').strip() or None

    def _write_client_id(self, client_id: str) -> None:
        value = client_id.strip()
        if not value:
            raise ConfigurationError('OAuth registration returned an empty client_id')
        path: Path = self._configuration.client_id_file
        temporary = path.with_name(f'.{path.name}.tmp')
        temporary.write_text(f'{value}\n', encoding='utf-8')
        temporary.chmod(384)
        temporary.replace(path)

    def _resource(self, request: A2AClientSecurityRequest) -> str:
        interfaces = tuple(request.agent_card.supported_interfaces)
        if not interfaces:
            raise ConfigurationError('A2A Agent Card has no supported interface')
        parsed = urlsplit(interfaces[0].url)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), '', ''))
