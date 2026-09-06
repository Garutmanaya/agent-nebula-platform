"""Immutable metrics snapshots exposed by the runtime operations layer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TimingSnapshot(BaseModel):
    """Summarize observed operation durations in seconds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    count: int = 0
    total_seconds: float = 0.0
    minimum_seconds: float | None = None
    maximum_seconds: float | None = None


class MetricsSnapshot(BaseModel):
    """Represent one point-in-time metrics registry snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    counters: dict[str, float] = Field(default_factory=dict)
    gauges: dict[str, float] = Field(default_factory=dict)
    timings: dict[str, TimingSnapshot] = Field(default_factory=dict)
