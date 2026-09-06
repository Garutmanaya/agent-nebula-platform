"""Scope-enforced skill authentication and invocation orchestration."""

from __future__ import annotations

from agent_nebula_platform.platform.errors import AuthenticationError
from agent_nebula_platform.security.oauth.protected_resource import (
    AuthorizedRequestContext,
    ProtectedResourceRequest,
    ProtectedResourceService,
)

from .models import SkillInvocation, SkillResult
from .registry import SkillRegistry


class SkillInvocationService:
    """Authenticate protected requests before dispatching business handlers."""

    def __init__(
        self,
        *,
        registry: SkillRegistry,
        protected_resource: ProtectedResourceService | None = None,
    ) -> None:
        self._registry = registry
        self._protected_resource = protected_resource

    async def invoke(
        self,
        *,
        skill_id: str,
        payload: dict[str, object],
        access_token: str | None = None,
        dpop_proof: str | None = None,
        http_method: str,
        target_uri: str,
        nonce_context: str | None = None,
    ) -> SkillResult:
        """Authorize exact method scopes and invoke the selected business skill."""

        security = self.authorize(
            skill_id=skill_id,
            access_token=access_token,
            dpop_proof=dpop_proof,
            http_method=http_method,
            target_uri=target_uri,
            nonce_context=nonce_context,
        )
        return await self.invoke_authorized(
            skill_id=skill_id,
            payload=payload,
            security=security,
        )

    def authorize(
        self,
        *,
        skill_id: str,
        access_token: str | None,
        dpop_proof: str | None,
        http_method: str,
        target_uri: str,
        nonce_context: str | None = None,
    ) -> AuthorizedRequestContext | None:
        """Authenticate one request and enforce the selected skill's exact scopes."""

        definition = self._registry.require(skill_id)
        if not definition.required_scopes:
            return None
        return self.authenticate_request(
            access_token=access_token,
            dpop_proof=dpop_proof,
            http_method=http_method,
            target_uri=target_uri,
            required_scopes=definition.required_scopes,
            nonce_context=nonce_context,
        )

    def authenticate_request(
        self,
        *,
        access_token: str | None,
        dpop_proof: str | None,
        http_method: str,
        target_uri: str,
        required_scopes: tuple[str, ...] = (),
        nonce_context: str | None = None,
    ) -> AuthorizedRequestContext:
        """Authenticate a protected control request without selecting a skill."""

        if self._protected_resource is None or not access_token or not dpop_proof:
            raise AuthenticationError(
                "Protected request requires an access token and DPoP proof"
            )
        return self._protected_resource.authenticate(
            ProtectedResourceRequest(
                access_token=access_token,
                dpop_proof=dpop_proof,
                http_method=http_method,
                target_uri=target_uri,
                required_scopes=required_scopes,
                nonce_context=nonce_context,
            )
        )

    async def invoke_authorized(
        self,
        *,
        skill_id: str,
        payload: dict[str, object],
        security: AuthorizedRequestContext | None,
    ) -> SkillResult:
        """Invoke a skill after its request security has already been validated."""

        self._registry.require(skill_id)
        return await self._registry.invoke(
            SkillInvocation(
                skill_id=skill_id,
                payload=dict(payload),
                security=security,
            )
        )
