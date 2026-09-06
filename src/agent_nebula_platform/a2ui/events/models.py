"""Typed persisted A2UI session event records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class A2UISessionEvent(BaseModel):
    """Represent one non-secret session transition for diagnostics and replay."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str = Field(min_length=1, max_length=200)
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
