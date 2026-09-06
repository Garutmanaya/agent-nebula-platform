"""Health and readiness contracts for embedded agent servers."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class HealthStatus(BaseModel):
    """Represent one health or readiness decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    ready: bool
    details: dict[str, str] = Field(default_factory=dict)


class HealthProvider(Protocol):
    """Supply host-specific liveness and readiness state."""

    def health(self) -> HealthStatus | Awaitable[HealthStatus]:
        """Return current liveness state."""

    def readiness(self) -> HealthStatus | Awaitable[HealthStatus]:
        """Return current readiness state."""


class StaticHealthProvider:
    """Provide healthy defaults for simple agents without external dependencies."""

    def health(self) -> HealthStatus:
        """Return a healthy liveness response."""

        return HealthStatus(status="healthy", ready=True)

    def readiness(self) -> HealthStatus:
        """Return a ready response."""

        return HealthStatus(status="ready", ready=True)
