"""Runtime-owned A2UI session engine and state transitions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from agent_nebula_platform.a2ui.data_model import A2UIDataModelService
from agent_nebula_platform.a2ui.surfaces import A2UISurfaceManager
from agent_nebula_platform.platform.events import EventSink, RuntimeEvent

from .models import (
    A2UIActionRecord,
    A2UISessionSnapshot,
    A2UISessionStatus,
    A2UISurfaceFrame,
    A2UITaskReference,
)
from .store import A2UISessionStore


class A2UISessionService:
    """Own persistent A2UI sessions, surfaces, data, actions, and tasks."""

    def __init__(
        self,
        *,
        store: A2UISessionStore,
        events: EventSink,
        max_history: int = 50,
        max_actions: int = 200,
    ) -> None:
        """Initialize the session engine and deterministic transition services."""

        self._store = store
        self._events = events
        self._max_actions = max_actions
        self._surfaces = A2UISurfaceManager(max_history=max_history)
        self._data_models = A2UIDataModelService()

    async def create(self, *, renderer: dict[str, Any]) -> A2UISessionSnapshot:
        """Create one isolated renderer session."""

        session = await self._store.create(A2UISessionSnapshot(renderer=dict(renderer)))
        self._emit("a2ui.session.created", session_id=session.session_id)
        return session

    async def get(self, session_id: str) -> A2UISessionSnapshot:
        """Return one persisted session snapshot."""

        return await self._store.get(session_id)

    async def resume(self, session_id: str) -> A2UISessionSnapshot:
        """Resume a suspended session while rejecting closed sessions."""

        session = await self.get(session_id)
        if session.status == A2UISessionStatus.CLOSED:
            raise ValueError("Closed A2UI session cannot be resumed")
        updated = session.model_copy(
            update={
                "status": A2UISessionStatus.ACTIVE,
                "updated_at": self._now(),
            }
        )
        await self._store.save(updated)
        self._emit("a2ui.session.resumed", session_id=session_id)
        return updated

    async def close(self, session_id: str) -> A2UISessionSnapshot:
        """Close a session while preserving its audit and resume history."""

        session = await self.get(session_id)
        updated = session.model_copy(
            update={
                "status": A2UISessionStatus.CLOSED,
                "updated_at": self._now(),
            }
        )
        await self._store.save(updated)
        self._emit("a2ui.session.closed", session_id=session_id)
        return updated

    async def select_agent(
        self,
        session_id: str,
        agent_id: str,
    ) -> A2UISessionSnapshot:
        """Select an Agent and retain it as a multi-agent participant."""

        session = await self.get(session_id)
        participants = tuple(dict.fromkeys((*session.participant_agent_ids, agent_id)))
        updated = session.model_copy(
            update={
                "selected_agent_id": agent_id,
                "participant_agent_ids": participants,
                "updated_at": self._now(),
            }
        )
        await self._store.save(updated)
        self._emit(
            "a2ui.session.agent_selected",
            session_id=session_id,
            agent_id=agent_id,
        )
        return updated

    async def apply_surface(
        self,
        session_id: str,
        frame: A2UISurfaceFrame,
    ) -> A2UISessionSnapshot:
        """Apply one validated surface transition to the session stack."""

        session = await self.get(session_id)
        transition = self._surfaces.apply(
            session.surfaces,
            session.cursor,
            frame,
        )
        participants = tuple(
            dict.fromkeys((*session.participant_agent_ids, frame.owner_agent_id))
        )
        updated = session.model_copy(
            update={
                "surfaces": transition.surfaces,
                "cursor": transition.cursor,
                "participant_agent_ids": participants,
                "updated_at": self._now(),
            }
        )
        await self._store.save(updated)
        self._emit(
            "a2ui.surface.applied",
            session_id=session_id,
            surface_id=frame.surface_id,
            mode=frame.mode.value,
        )
        return updated

    async def back(self, session_id: str) -> A2UISessionSnapshot:
        """Move the session cursor to the previous surface."""

        session = await self.get(session_id)
        cursor = max(0, session.cursor - 1) if session.surfaces else -1
        updated = session.model_copy(
            update={"cursor": cursor, "updated_at": self._now()}
        )
        await self._store.save(updated)
        self._emit("a2ui.navigation.back", session_id=session_id, cursor=cursor)
        return updated

    async def forward(self, session_id: str) -> A2UISessionSnapshot:
        """Move the session cursor to the next surface."""

        session = await self.get(session_id)
        cursor = (
            min(len(session.surfaces) - 1, session.cursor + 1)
            if session.surfaces
            else -1
        )
        updated = session.model_copy(
            update={"cursor": cursor, "updated_at": self._now()}
        )
        await self._store.save(updated)
        self._emit(
            "a2ui.navigation.forward",
            session_id=session_id,
            cursor=cursor,
        )
        return updated

    async def update_data_model(
        self,
        session_id: str,
        patch: dict[str, Any],
    ) -> A2UISessionSnapshot:
        """Deep-merge one renderer or provider data-model update."""

        session = await self.get(session_id)
        data = self._data_models.merge(session.data_model, patch)
        updated = session.model_copy(
            update={"data_model": data, "updated_at": self._now()}
        )
        await self._store.save(updated)
        self._emit("a2ui.data_model.updated", session_id=session_id)
        return updated

    async def record_action(
        self,
        session_id: str,
        action: A2UIActionRecord,
    ) -> A2UISessionSnapshot:
        """Persist one non-secret renderer action before dispatch."""

        session = await self.get(session_id)
        actions = (*session.actions, action)[-self._max_actions :]
        updated = session.model_copy(
            update={"actions": actions, "updated_at": self._now()}
        )
        await self._store.save(updated)
        self._emit(
            "a2ui.action.recorded",
            session_id=session_id,
            action=action.name,
        )
        return updated

    async def attach_task(
        self,
        session_id: str,
        task: A2UITaskReference,
    ) -> A2UISessionSnapshot:
        """Attach or replace one provider A2A task/context reference."""

        session = await self.get(session_id)
        tasks = [
            item
            for item in session.tasks
            if not (item.agent_id == task.agent_id and item.task_id == task.task_id)
        ]
        tasks.append(task)
        updated = session.model_copy(
            update={"tasks": tuple(tasks), "updated_at": self._now()}
        )
        await self._store.save(updated)
        self._emit(
            "a2ui.task.attached",
            session_id=session_id,
            agent_id=task.agent_id,
            task_id=task.task_id,
        )
        return updated

    async def delete(self, session_id: str) -> None:
        """Physically delete one session from the configured store."""

        await self._store.delete(session_id)
        self._emit("a2ui.session.deleted", session_id=session_id)

    @staticmethod
    def _now() -> datetime:
        """Return one timezone-aware transition timestamp."""

        return datetime.now(UTC)

    def _emit(self, name: str, **attributes: object) -> None:
        """Emit one structured Runtime event without secret material."""

        self._events.emit(RuntimeEvent(name, attributes))
