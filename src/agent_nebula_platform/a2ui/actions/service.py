"""Transport-neutral A2UI action dispatch coordination."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from agent_nebula_platform.a2ui.session import A2UIActionRecord, A2UISessionService

ActionHandler = Callable[
    [A2UIActionRecord, dict[str, Any]],
    Awaitable[Any],
]


class A2UIActionDispatcher:
    """Record state before delegating secured provider invocation."""

    def __init__(self, sessions: A2UISessionService) -> None:
        """Inject the Runtime-owned session engine."""

        self._sessions = sessions

    async def dispatch(
        self,
        *,
        session_id: str,
        action: A2UIActionRecord,
        data_model_patch: dict[str, Any],
        handler: ActionHandler,
    ) -> Any:
        """Persist action/data state, then invoke the caller-supplied handler."""

        await self._sessions.record_action(session_id, action)
        if data_model_patch:
            await self._sessions.update_data_model(
                session_id,
                data_model_patch,
            )
        return await handler(action, data_model_patch)
