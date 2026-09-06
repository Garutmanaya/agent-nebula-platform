"""Scheduler job, trigger, and execution-state models."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

from agent_nebula_platform.platform.retry import RetryPolicy

JobHandler = Callable[[], Awaitable[None]]


class JobTriggerType(StrEnum):
    """Supported built-in scheduling modes."""

    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    ONCE = "once"
    INTERVAL = "interval"


@dataclass(frozen=True, slots=True)
class ScheduledJob:
    """Describe one host-neutral asynchronous background job."""

    name: str
    handler: JobHandler
    trigger: JobTriggerType
    interval_seconds: float | None = None
    delay_seconds: float = 0.0
    required: bool = False
    retry_policy: RetryPolicy | None = None

    def validate(self) -> None:
        """Reject duplicate-prone or impossible scheduling definitions."""

        if not self.name or not self.name.strip():
            raise ValueError("Scheduled job name cannot be empty")
        if self.delay_seconds < 0:
            raise ValueError("Scheduled job delay cannot be negative")
        if self.trigger is JobTriggerType.INTERVAL:
            if self.interval_seconds is None or self.interval_seconds <= 0:
                raise ValueError("Interval jobs require a positive interval_seconds")
        elif self.interval_seconds is not None:
            raise ValueError("interval_seconds is valid only for interval jobs")
        if self.retry_policy is not None:
            self.retry_policy.validate()
