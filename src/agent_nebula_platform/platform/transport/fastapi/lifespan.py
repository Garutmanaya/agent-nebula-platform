"""FastAPI lifespan integration for the pre-server Agent Runtime phase."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

if TYPE_CHECKING:
    from agent_nebula_platform.platform.runtime import AgentRuntime


def runtime_lifespan(runtime: AgentRuntime) -> Any:
    """Return a lifespan handler that prepares routes before listener startup.

    Post-server plugins are intentionally not started here because FastAPI's
    startup lifespan completes before Uvicorn exposes a reliable listener-ready
    signal. Standalone server ownership starts that phase after Uvicorn reports
    ``started``; embedded hosts must signal readiness explicitly.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        del app
        await runtime.initialize_pre_server()
        try:
            yield
        finally:
            await runtime.close()

    return lifespan
