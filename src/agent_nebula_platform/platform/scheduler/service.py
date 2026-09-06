"""Gracefully managed asynchronous scheduler for runtime background jobs."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from agent_nebula_platform.platform.events import EventSink, RuntimeEvent
from agent_nebula_platform.platform.retry import execute_with_retry

from .models import JobTriggerType, ScheduledJob


class RuntimeScheduler:
    """Execute registered startup, shutdown, one-shot, and interval jobs."""

    def __init__(self, *, jobs: Iterable[ScheduledJob], events: EventSink) -> None:
        self._jobs = tuple(jobs)
        self._events = events
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._started = False
        names: set[str] = set()
        for job in self._jobs:
            job.validate()
            if job.name in names:
                raise ValueError(f"Scheduled job is already registered: {job.name}")
            names.add(job.name)

    @property
    def running_jobs(self) -> tuple[str, ...]:
        """Return names of currently active asynchronous job loops."""

        return tuple(name for name, task in self._tasks.items() if not task.done())

    async def start(self) -> None:
        """Run startup jobs and launch one-shot and interval jobs."""

        if self._started:
            return
        self._started = True
        for job in self._jobs:
            if job.trigger is JobTriggerType.STARTUP:
                await self._execute(job)
        for job in self._jobs:
            if job.trigger is JobTriggerType.ONCE:
                self._tasks[job.name] = asyncio.create_task(
                    self._run_once(job), name=job.name
                )
            elif job.trigger is JobTriggerType.INTERVAL:
                self._tasks[job.name] = asyncio.create_task(
                    self._run_interval(job), name=job.name
                )

    async def stop(self) -> None:
        """Cancel active jobs, await termination, then run shutdown jobs."""

        if not self._started:
            return
        for task in self._tasks.values():
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        for job in self._jobs:
            if job.trigger is JobTriggerType.SHUTDOWN:
                await self._execute(job)
        self._started = False

    async def _run_once(self, job: ScheduledJob) -> None:
        """Execute one delayed job exactly once unless shutdown cancels it."""

        if job.delay_seconds:
            await asyncio.sleep(job.delay_seconds)
        await self._execute(job)

    async def _run_interval(self, job: ScheduledJob) -> None:
        """Execute one job repeatedly until scheduler shutdown."""

        if job.delay_seconds:
            await asyncio.sleep(job.delay_seconds)
        while True:
            await self._execute(job)
            await asyncio.sleep(job.interval_seconds or 0)

    async def _execute(self, job: ScheduledJob) -> None:
        """Execute a job with optional retry and required-job semantics."""

        self._events.emit(
            RuntimeEvent("runtime.scheduler.job_started", {"job": job.name})
        )
        try:
            if job.retry_policy is None:
                await job.handler()
            else:
                await execute_with_retry(job.handler, policy=job.retry_policy)
        except Exception:
            self._events.emit(
                RuntimeEvent(
                    "runtime.scheduler.job_failed",
                    {"job": job.name, "required": job.required},
                )
            )
            if job.required:
                raise
        else:
            self._events.emit(
                RuntimeEvent("runtime.scheduler.job_completed", {"job": job.name})
            )
