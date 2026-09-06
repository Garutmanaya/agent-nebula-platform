"""Lifecycle integration for attaching Platform runtime to caller-owned FastAPI apps."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from agent_nebula_platform.platform.presets import RuntimeApplication


class FastApiLifecycleInstaller:
    """Compose Platform lifecycle with an existing FastAPI lifespan."""

    def install(
        self,
        *,
        app: FastAPI,
        runtime_application: RuntimeApplication,
        original_lifespan: Callable[[FastAPI], Any],
    ) -> None:
        """Preserve host lifespan while initializing and closing Platform plugins."""

        runtime = runtime_application.runtime

        @asynccontextmanager
        async def combined_lifespan(current_app: FastAPI) -> AsyncIterator[None]:
            post_server_task: asyncio.Task[None] | None = None
            async with original_lifespan(current_app):
                await runtime.initialize_pre_server()
                post_server_task = asyncio.create_task(
                    runtime.initialize_post_server(),
                    name="agent-nebula-platform-post-server",
                )
                try:
                    yield
                finally:
                    if post_server_task is not None:
                        if not post_server_task.done():
                            post_server_task.cancel()
                        try:
                            await post_server_task
                        except asyncio.CancelledError:
                            pass
                    await runtime.close()

        app.router.lifespan_context = combined_lifespan
