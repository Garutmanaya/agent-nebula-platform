"""Transport-neutral REST skill invocation adapter."""

from __future__ import annotations

from typing import Any

from agent_nebula_platform.skills import SkillInvocationService, SkillResult


class RestSkillAdapter:
    """Translate one REST-style method invocation into the shared skill service."""

    def __init__(self, service: SkillInvocationService) -> None:
        self._service = service

    async def invoke(
        self,
        *,
        skill_id: str,
        payload: dict[str, Any],
        access_token: str | None,
        dpop_proof: str | None,
        http_method: str,
        target_uri: str,
        nonce_context: str | None = None,
    ) -> SkillResult:
        """Invoke a skill through the runtime's common authorization boundary."""

        return await self._service.invoke(
            skill_id=skill_id,
            payload=payload,
            access_token=access_token,
            dpop_proof=dpop_proof,
            http_method=http_method,
            target_uri=target_uri,
            nonce_context=nonce_context,
        )
