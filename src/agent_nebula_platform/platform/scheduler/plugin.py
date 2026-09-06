"""Runtime scheduler plugin for managed background jobs."""

from __future__ import annotations

from collections.abc import Iterable

from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.health import HealthStatus
from agent_nebula_platform.platform.plugins.base import RuntimePlugin
from agent_nebula_platform.platform.scheduler import RuntimeScheduler, ScheduledJob


class SchedulerPlugin(RuntimePlugin):
    """Start and stop registered jobs under the runtime lifecycle."""

    def __init__(self, jobs: Iterable[ScheduledJob], *, required: bool = False) -> None:
        self._jobs = tuple(jobs)
        self._required = required
        self._scheduler: RuntimeScheduler | None = None

    @property
    def name(self) -> str:
        """Return the stable plugin identifier."""

        return "operations.scheduler"

    @property
    def required(self) -> bool:
        """Return whether scheduler startup failure is fatal."""

        return self._required

    async def initialize(self, context: RuntimeContext) -> None:
        """Create the scheduler, run startup jobs, and launch background jobs."""

        scheduler = RuntimeScheduler(jobs=self._jobs, events=context.events)
        await scheduler.start()
        self._scheduler = scheduler
        context.services.register("scheduler", scheduler)

    async def close(self, context: RuntimeContext) -> None:
        """Cancel background jobs and run shutdown jobs before removal."""

        if self._scheduler is not None:
            await self._scheduler.stop()
        context.services.remove("scheduler")
        self._scheduler = None

    async def health(self) -> HealthStatus:
        """Report scheduler availability and active-loop count."""

        if self._scheduler is None:
            return HealthStatus(status="not_initialized", ready=False)
        return HealthStatus(
            status="healthy",
            ready=True,
            details={"running_jobs": str(len(self._scheduler.running_jobs))},
        )
