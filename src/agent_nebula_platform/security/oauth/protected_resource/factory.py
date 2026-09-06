"""Runtime-owned construction of SDK-backed protected-resource security."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from agent_nebula_sdk.adapters.httpx_transport import HttpxTransport
from agent_nebula_sdk.jose.jwks.cache import JwksCache
from agent_nebula_sdk.jose.jwks.resolver import RemoteJwksResolver
from agent_nebula_sdk.jose.jwks.uri_policy import JwksUriPolicy
from agent_nebula_sdk.oauth.resource_server import ResourceServerFacade
from agent_nebula_sdk.oauth.rfc8707 import ResourceAudienceValidator
from agent_nebula_sdk.oauth.rfc9068 import JwtAccessTokenValidator, Rfc9068Policy
from agent_nebula_sdk.oauth.rfc9449 import (
    DpopProofValidator,
    DpopTargetUriNormalizer,
    DpopTokenBindingService,
    InMemoryDpopReplayStore,
    Rfc9449Policy,
)
from agent_nebula_sdk.ports.clock import SystemClock

from agent_nebula_platform.platform.events import EventSink

from .policy import ExactScopeAuthorizationPolicy
from .service import ProtectedResourceService


class NebulaJwksVerificationKeyResolver:
    """Adapt the SDK remote JWKS resolver to RFC 9068 key resolution."""

    def __init__(self, *, jwks_uri: str, resolver: RemoteJwksResolver) -> None:
        self._jwks_uri = jwks_uri
        self._resolver = resolver

    def resolve(self, *, issuer: str, key_id: str, algorithm: str):
        """Resolve one trusted signing key by JOSE metadata."""

        del issuer
        return self._resolver.resolve_key(
            self._jwks_uri,
            kid=key_id,
            alg=algorithm,
            use="sig",
        )


@dataclass(slots=True)
class ProtectedResourceRuntime:
    """Own a protected-resource service and its SDK JWKS transport."""

    service: ProtectedResourceService
    transport: HttpxTransport

    async def close(self) -> None:
        """Close the synchronous SDK transport during Runtime shutdown."""

        self.transport.close()


class ProtectedResourceRuntimeFactory:
    """Compose provider security from Agent Nebula SDK implementations."""

    def build(
        self,
        *,
        resource: str,
        issuer: str,
        jwks_uri: str,
        ca_file: str,
        access_token_algorithms: tuple[str, ...],
        dpop_algorithms: tuple[str, ...],
        events: EventSink,
        dpop_required: bool = True,
        timeout_seconds: float = 10.0,
        jwks_cache_seconds: int = 300,
        clock_skew_seconds: int = 30,
        dpop_maximum_age_seconds: int = 300,
        allow_private_jwks_networks: bool = True,
    ) -> ProtectedResourceRuntime:
        """Build RFC 8707, RFC 9068, and RFC 9449 validation services."""

        clock = SystemClock()
        transport = HttpxTransport(timeout_seconds=timeout_seconds, verify=ca_file)
        resolver = RemoteJwksResolver(
            transport=transport,
            cache=JwksCache(clock=clock),
            uri_policy=JwksUriPolicy(
                allow_http_for_loopback=False,
                allow_private_networks=allow_private_jwks_networks,
            ),
            default_ttl=timedelta(seconds=jwks_cache_seconds),
        )
        token_policy = Rfc9068Policy(
            allowed_algorithms=frozenset(access_token_algorithms),
            clock_skew=timedelta(seconds=clock_skew_seconds),
        )
        dpop_policy = Rfc9449Policy(
            allowed_algorithms=frozenset(dpop_algorithms),
            maximum_proof_age=timedelta(seconds=dpop_maximum_age_seconds),
            clock_skew=timedelta(seconds=clock_skew_seconds),
            require_https_target=True,
            require_nonce=False,
        )
        facade = ResourceServerFacade(
            token_validator=JwtAccessTokenValidator(
                clock=clock,
                policy=token_policy,
                key_resolver=NebulaJwksVerificationKeyResolver(
                    jwks_uri=jwks_uri,
                    resolver=resolver,
                ),
            ),
            dpop_validator=DpopProofValidator(
                clock=clock,
                policy=dpop_policy,
                replay_store=InMemoryDpopReplayStore(clock=clock),
                uri_normalizer=DpopTargetUriNormalizer(policy=dpop_policy),
            ),
            audience_validator=ResourceAudienceValidator(
                expected_audience=resource,
                require_single_audience=True,
            ),
            binding_service=DpopTokenBindingService(),
        )
        return ProtectedResourceRuntime(
            service=ProtectedResourceService(
                expected_issuer=issuer,
                facade=facade,
                policy=ExactScopeAuthorizationPolicy(),
                events=events,
                dpop_required=dpop_required,
            ),
            transport=transport,
        )
