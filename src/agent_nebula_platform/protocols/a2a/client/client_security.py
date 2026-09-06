"""Dynamic A2A 1.0 client security negotiation and request interception.

Runtime interprets the remote Agent Card. Credential acquisition is delegated to
scheme-specific providers so protocol algorithms remain in agent-nebula-sdk.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from a2a.client.client import ClientCallContext
from a2a.client.interceptors import AfterArgs, BeforeArgs, ClientCallInterceptor
from a2a.client.service_parameters import ServiceParameters
from a2a.types import AgentCard, SecurityScheme

from agent_nebula_platform.platform.errors import (
    AuthenticationError,
    ConfigurationError,
)


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

    def resolve(
        self, *, agent_card: AgentCard, method: str, skill_id: str | None = None
    ) -> A2AResolvedSecurityRequirement:
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
                raise ConfigurationError(
                    f"A2A skill is not advertised by the remote agent: {skill_id}"
                )
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
                    raise ConfigurationError(
                        "A2A Agent Card security requirement references an undefined scheme",
                        details={"scheme_name": scheme_name},
                    )
                scheme = schemes[scheme_name]
                request = A2AClientSecurityRequest(
                    scheme_name=scheme_name,
                    scheme=scheme,
                    required_values=tuple(values.list),
                    agent_card=agent_card,
                    method=method,
                )
                if self._provider_for(request) is None:
                    failures.append(scheme_name)
                    satisfiable = False
                    break
                resolved.append(request)
            if satisfiable:
                return A2AResolvedSecurityRequirement(tuple(resolved))

        raise AuthenticationError(
            "No advertised A2A security requirement can be satisfied by configured credentials",
            details={"unavailable_schemes": sorted(set(failures))},
        )

    def provider_for(
        self, request: A2AClientSecurityRequest
    ) -> A2AClientCredentialProvider:
        """Return the provider selected by official SecurityScheme oneof type."""
        provider = self._provider_for(request)
        if provider is None:
            raise AuthenticationError(
                f"No credential provider can satisfy A2A scheme {request.scheme_name!r}"
            )
        return provider

    async def close(self) -> None:
        """Close resources owned by configured credential providers."""
        for provider in self._providers:
            close = getattr(provider, "close", None)
            if close is None:
                continue
            result = close()
            if hasattr(result, "__await__"):
                await result

    def _provider_for(
        self, request: A2AClientSecurityRequest
    ) -> A2AClientCredentialProvider | None:
        scheme_type = request.scheme.WhichOneof("scheme")
        for provider in self._providers:
            if provider.scheme_type == scheme_type and provider.can_satisfy(request):
                return provider
        return None


class A2AClientSecurityInterceptor(ClientCallInterceptor):
    """Apply a complete negotiated A2A security requirement to every client call."""

    def __init__(self, resolver: A2AClientSecurityResolver) -> None:
        self._resolver = resolver

    async def before(self, args: BeforeArgs) -> None:
        """Resolve OR-of-AND requirements and merge every credential in the selected AND-group."""
        skill_id = None
        if args.context is not None:
            value = args.context.state.get("agent_nebula.a2a.skill_id")
            if isinstance(value, str):
                skill_id = value
        resolved = self._resolver.resolve(
            agent_card=args.agent_card, method=args.method, skill_id=skill_id
        )
        if not resolved.schemes:
            return
        context = args.context or ClientCallContext()
        parameters = ServiceParameters()
        if context.service_parameters:
            parameters.update(context.service_parameters)

        for request in resolved.schemes:
            credential = await self._resolver.provider_for(request).acquire(request)
            if credential.query_parameters or credential.cookie_parameters:
                raise ConfigurationError(
                    "The official A2A 1.0 client interceptor surface cannot safely apply query/cookie credentials",
                    details={"scheme_name": request.scheme_name},
                )
            for name, value in credential.headers:
                existing = parameters.get(name)
                if existing is not None and existing != value:
                    raise AuthenticationError(
                        "A2A compound security requirements produced conflicting headers",
                        details={"header": name},
                    )
                parameters[name] = value
        context.service_parameters = parameters
        args.context = context

    async def apply_http_request_security(
        self,
        *,
        agent_card: AgentCard,
        http_method: str,
        target_uri: str,
        headers,
        skill_id: str | None = None,
    ) -> None:
        """Refresh request-bound credentials using the final HTTP method and URI.

        The official A2A interceptor runs before the transport has constructed
        its concrete HTTP request. RFC 9449 DPoP therefore needs this final
        transport hook so ``htm`` and ``htu`` describe the request that actually
        carries the proof. Other credentials remain unchanged.
        """

        resolved = self._resolver.resolve(
            agent_card=agent_card, method="http_request", skill_id=skill_id
        )
        normalized_target = _dpop_target_uri(target_uri)
        for security_request in resolved.schemes:
            provider = self._resolver.provider_for(security_request)
            acquire_for_target = getattr(provider, "acquire_for_request_target", None)
            if acquire_for_target is None:
                continue
            credential = await acquire_for_target(
                security_request,
                http_method=http_method,
                target_uri=normalized_target,
            )
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
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
