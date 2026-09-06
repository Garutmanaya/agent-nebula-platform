"""Protected-resource authentication using agent-nebula-sdk."""

from __future__ import annotations

from agent_nebula_sdk.oauth.resource_server import ResourceServerFacade

from agent_nebula_platform.platform.errors import AuthenticationError
from agent_nebula_platform.platform.events import EventSink, RuntimeEvent

from .models import AuthorizedRequestContext, ProtectedResourceRequest
from .ports import ProtectedResourceAuthorizationPolicy


class ProtectedResourceService:
    """Authenticate DPoP-bound requests and apply provider-local authorization."""

    def __init__(
        self,
        *,
        expected_issuer: str,
        facade: ResourceServerFacade,
        policy: ProtectedResourceAuthorizationPolicy,
        events: EventSink,
        dpop_required: bool = True,
    ) -> None:
        self._expected_issuer = str(expected_issuer)
        self._facade = facade
        self._policy = policy
        self._events = events
        self._dpop_required = dpop_required

    @property
    def dpop_required(self) -> bool:
        """Return whether RFC 9728 policy requires DPoP-bound access tokens."""

        return self._dpop_required

    def authenticate(
        self, request: ProtectedResourceRequest
    ) -> AuthorizedRequestContext:
        """Validate token, audience, DPoP binding, replay state, and exact scopes."""

        if self._dpop_required:
            if not request.dpop_proof:
                raise AuthenticationError(
                    "DPoP proof is required by protected-resource policy"
                )
            security = self._facade.authenticate_request(
                access_token=request.access_token,
                dpop_proof=request.dpop_proof,
                http_method=request.http_method,
                target_uri=request.target_uri,
                expected_issuer=self._expected_issuer,
                nonce_context=request.nonce_context,
            )
        else:
            security = self._facade.authenticate_bearer_request(
                access_token=request.access_token,
                expected_issuer=self._expected_issuer,
            )
        granted = tuple(dict.fromkeys((security.claims.scope or "").split()))
        context = AuthorizedRequestContext(
            subject=security.subject,
            client_id=security.client_id,
            granted_scopes=granted,
            token_claims=security.claims,
            dpop_proof=security.dpop_proof,
        )
        self._policy.authorize(context=context, required_scopes=request.required_scopes)
        self._events.emit(
            RuntimeEvent(
                "protected_resource.request.authorized",
                {
                    "client_id": security.client_id,
                    "required_scope_count": len(request.required_scopes),
                },
            )
        )
        return context
