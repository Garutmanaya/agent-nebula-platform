"""OAuth client-credentials orchestration using agent-nebula-sdk."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from agent_nebula_sdk.oauth.client import ClientTokenRequest, OAuthClientFacade

from agent_nebula_platform.platform.errors import RemoteServiceError
from agent_nebula_platform.platform.events import EventSink, RuntimeEvent
from agent_nebula_platform.platform.execution_trace import record_execution_event

from .models import OAuthToken, OAuthTokenRequest, ProtectedRequest
from .ports import OAuthClientIdentityProvider, OAuthTokenCache, OAuthTokenTransport


class OAuthClientService:
    """Acquire, cache, and apply resource-specific DPoP-bound access tokens."""

    def __init__(
        self,
        *,
        token_endpoint: str,
        facade: OAuthClientFacade,
        identity: OAuthClientIdentityProvider,
        transport: OAuthTokenTransport,
        cache: OAuthTokenCache,
        events: EventSink,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        expiry_skew_seconds: int = 15,
    ) -> None:
        """Initialize the OAuth client service and its managed dependencies."""

        self._token_endpoint = str(token_endpoint)
        self._facade = facade
        self._identity = identity
        self._transport = transport
        self._cache = cache
        self._events = events
        self._clock = clock
        self._expiry_skew = expiry_skew_seconds

    async def token(self, request: OAuthTokenRequest) -> OAuthToken:
        """Return a cached or newly issued token for one exact resource request."""

        cache_key = self._cache_key(request)
        now = self._clock()
        cached = self._cache.get(cache_key, now=now)

        if cached is not None:
            record_execution_event(
                {
                    "type": "OAUTH_TOKEN_RESPONSE",
                    "source": "OAUTH_CLIENT_CACHE",
                    "component": "OAUTH",
                    "direction": "RESPONSE",
                    "target": "ORCHESTRATOR",
                    "status": "SUCCEEDED",
                    "duration_ms": 0,
                    "response": {
                        "resource": request.resource,
                        "issued_scopes": list(request.scopes),
                        "token_type": "DPoP",
                        "dpop_bound": True,
                        "cache_hit": True,
                    },
                    "details": {"token_endpoint": self._token_endpoint},
                }
            )
            self._events.emit(
                RuntimeEvent(
                    "oauth.token.cache_hit",
                    {
                        "resource": request.resource,
                        "scopes": list(request.scopes),
                        "scope_count": len(request.scopes),
                    },
                )
            )
            return cached

        # Trace the logical OAuth request separately from the lower-level HTTP
        # transport. The trace deliberately includes only resource/scope/auth
        # metadata; private-key JWT assertions and DPoP proofs never enter it.
        token_started = time.perf_counter()
        record_execution_event(
            {
                "type": "OAUTH_TOKEN_REQUEST",
                "source": "ORCHESTRATOR",
                "component": "OAUTH",
                "direction": "REQUEST",
                "target": self._token_endpoint,
                "status": "STARTED",
                "duration_ms": 0,
                "request": {
                    "grant_type": "client_credentials",
                    "resource": request.resource,
                    "scopes": list(request.scopes),
                    "authentication_method": "private_key_jwt",
                    "dpop": "present",
                },
                "details": {"token_endpoint": self._token_endpoint},
            }
        )

        # Log only non-secret request metadata. Never log the private-key JWT,
        # DPoP proof, private keys, access token, or complete form payload.
        self._events.emit(
            RuntimeEvent(
                "oauth.token.request.started",
                {
                    "token_endpoint": self._token_endpoint,
                    "resource": request.resource,
                    "scopes": list(request.scopes),
                    "scope_count": len(request.scopes),
                },
            )
        )

        artifacts = self._facade.build_token_request(
            request=ClientTokenRequest(
                client_id=self._identity.client_id(),
                token_endpoint=self._token_endpoint,
                resource=request.resource,
                scope=request.scopes,
            ),
            authentication_key=self._identity.authentication_key(),
            dpop_key=self._identity.dpop_key(),
        )

        try:
            payload = await self._transport.request_token(
                token_endpoint=self._token_endpoint,
                form_fields=artifacts.form_fields,
                dpop_proof=artifacts.dpop_proof.proof,
            )
        except Exception as exc:
            record_execution_event(
                {
                    "type": "OAUTH_TOKEN_RESPONSE",
                    "source": "AGENT_NEBULA_OAUTH",
                    "component": "OAUTH",
                    "direction": "RESPONSE",
                    "target": "ORCHESTRATOR",
                    "status": "FAILED",
                    "duration_ms": max(
                        0, round((time.perf_counter() - token_started) * 1000)
                    ),
                    "response": {"error_type": type(exc).__name__},
                    "details": {
                        "token_endpoint": self._token_endpoint,
                        "resource": request.resource,
                        "requested_scopes": list(request.scopes),
                    },
                }
            )
            self._events.emit(
                RuntimeEvent(
                    "oauth.token.request.failed",
                    {
                        "token_endpoint": self._token_endpoint,
                        "resource": request.resource,
                        "scopes": list(request.scopes),
                        "scope_count": len(request.scopes),
                        "error_type": type(exc).__name__,
                    },
                )
            )
            raise

        token = self._parse_token(payload, now=now)
        self._cache.put(cache_key, token)

        record_execution_event(
            {
                "type": "OAUTH_TOKEN_RESPONSE",
                "source": "AGENT_NEBULA_OAUTH",
                "component": "OAUTH",
                "direction": "RESPONSE",
                "target": "ORCHESTRATOR",
                "status": "SUCCEEDED",
                "duration_ms": max(
                    0, round((time.perf_counter() - token_started) * 1000)
                ),
                "response": {
                    "resource": request.resource,
                    "requested_scopes": list(request.scopes),
                    "issued_scopes": list(token.scopes),
                    "token_type": token.token_type,
                    "dpop_bound": True,
                    "cache_hit": False,
                },
                "details": {"token_endpoint": self._token_endpoint},
            }
        )

        self._events.emit(
            RuntimeEvent(
                "oauth.token.received",
                {
                    "resource": request.resource,
                    "requested_scopes": list(request.scopes),
                    "requested_scope_count": len(request.scopes),
                    "issued_scopes": list(token.scopes),
                    "issued_scope_count": len(token.scopes),
                },
            )
        )

        return token

    async def protected_request(
        self,
        *,
        http_method: str,
        target_uri: str,
        resource: str,
        scopes: tuple[str, ...],
    ) -> ProtectedRequest:
        """Build authorization and DPoP headers for one protected request."""

        self._events.emit(
            RuntimeEvent(
                "oauth.protected_request.started",
                {
                    "http_method": http_method.upper(),
                    "target_uri": target_uri,
                    "resource": resource,
                    "scopes": list(scopes),
                    "scope_count": len(scopes),
                },
            )
        )

        token = await self.token(
            OAuthTokenRequest(
                resource=resource,
                scopes=scopes,
            )
        )

        artifacts = self._facade.build_protected_request(
            http_method=http_method,
            target_uri=target_uri,
            access_token=token.access_token,
            dpop_key=self._identity.dpop_key(),
        )
        record_execution_event(
            {
                "type": "DPOP_PROOF_CREATED",
                "source": "ORCHESTRATOR",
                "component": "DPOP",
                "direction": "INTERNAL",
                "target": target_uri,
                "status": "SUCCEEDED",
                "duration_ms": 0,
                "details": {
                    "http_method": http_method.upper(),
                    "target_uri": target_uri,
                    "resource": resource,
                    "scopes": list(scopes),
                    "dpop_key_thumbprint": self._identity.dpop_key_thumbprint(),
                    "proof": "<redacted>",
                },
            }
        )

        return ProtectedRequest(
            headers=artifacts.headers,
            token=token,
        )

    def _cache_key(self, request: OAuthTokenRequest) -> str:
        """Create a non-reversible cache key for one resource and scope set."""

        material = "\x1f".join(
            (
                request.resource,
                self._identity.dpop_key_thumbprint(),
                *sorted(request.scopes),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _parse_token(
        self,
        payload: dict[str, object],
        *,
        now: datetime,
    ) -> OAuthToken:
        """Validate and normalize one OAuth token endpoint response."""

        access_token = payload.get("access_token")
        token_type = payload.get("token_type")
        expires_in = payload.get("expires_in")

        if not isinstance(access_token, str) or not access_token:
            raise RemoteServiceError("OAuth token response is missing access_token")

        if not isinstance(token_type, str) or not token_type:
            raise RemoteServiceError("OAuth token response is missing token_type")

        try:
            seconds = int(expires_in)
        except (TypeError, ValueError) as exc:
            raise RemoteServiceError(
                "OAuth token response has invalid expires_in"
            ) from exc

        if seconds <= self._expiry_skew:
            raise RemoteServiceError("OAuth token lifetime is too short")

        raw_scope = payload.get("scope")
        scopes = tuple(dict.fromkeys(str(raw_scope or "").split()))

        return OAuthToken(
            access_token=access_token,
            token_type=token_type,
            expires_at=now + timedelta(seconds=seconds - self._expiry_skew),
            scopes=scopes,
        )
