"""First-class A2UI session, navigation, task, and participant models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class A2UISessionStatus(StrEnum):
    """Lifecycle states for one persisted A2UI interaction session."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class A2UISurfaceMode(StrEnum):
    """Supported deterministic surface-stack operations."""

    PUSH = "PUSH"
    REPLACE = "REPLACE"
    MODAL = "MODAL"
    APPEND = "APPEND"


class A2UISurfaceFrame(BaseModel):
    """Immutable renderer surface snapshot retained by one session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    surface_id: str = Field(min_length=1, max_length=200)
    owner_agent_id: str = Field(min_length=1, max_length=200)
    skill_id: str = Field(min_length=1, max_length=200)
    version: str | None = None
    mode: A2UISurfaceMode = A2UISurfaceMode.PUSH
    messages: tuple[dict[str, Any], ...] = ()
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class A2UIActionRecord(BaseModel):
    """Audit-safe record of one renderer action without credentials."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=1, max_length=200)
    surface_id: str = Field(min_length=1, max_length=200)
    owner_agent_id: str = Field(min_length=1, max_length=200)
    source_component_id: str | None = Field(default=None, max_length=200)
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class A2UITaskReference(BaseModel):
    """Track one provider-side A2A task or context within a UI session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_id: str = Field(min_length=1, max_length=200)
    task_id: str | None = Field(default=None, max_length=300)
    context_id: str | None = Field(default=None, max_length=300)
    status: str | None = Field(default=None, max_length=100)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class A2UISessionSnapshot(BaseModel):
    """Persistable state for a domain-neutral multi-agent A2UI interaction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    status: A2UISessionStatus = A2UISessionStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    selected_agent_id: str | None = None
    participant_agent_ids: tuple[str, ...] = ()
    renderer: dict[str, Any] = Field(default_factory=dict)
    surfaces: tuple[A2UISurfaceFrame, ...] = ()
    cursor: int = -1
    data_model: dict[str, Any] = Field(default_factory=dict)
    actions: tuple[A2UIActionRecord, ...] = ()
    tasks: tuple[A2UITaskReference, ...] = ()

    @property
    def current_surface(self) -> A2UISurfaceFrame | None:
        """Return the surface selected by the navigation cursor."""

        if self.cursor < 0 or self.cursor >= len(self.surfaces):
            return None
        return self.surfaces[self.cursor]
