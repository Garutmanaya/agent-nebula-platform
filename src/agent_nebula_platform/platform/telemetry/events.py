"""Structured telemetry event contracts for operational integrations."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TelemetrySeverity(StrEnum):
    """Stable severity values independent of one logging framework."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class TelemetryEvent(BaseModel):
    """Represent one non-secret structured runtime event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: str = Field(min_length=1, max_length=200)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    severity: TelemetrySeverity = TelemetrySeverity.INFO
    correlation_id: str | None = None
    task_id: str | None = None
    plugin: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
