"""Standalone Agent Runtime application and explicit server ownership."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI

from agent_nebula_platform.platform.runtime import AgentRuntime
from agent_nebula_platform.platform.transport.fastapi import (
    UvicornRuntimeServer,
    UvicornServerSettings,
    runtime_lifespan,
)

from .settings import StandaloneRuntimeSettings


@dataclass(frozen=True, slots=True)
class StandaloneAgent:
    """Bundle a composed runtime, FastAPI app, and validated server settings."""

    runtime: AgentRuntime
    app: FastAPI
    settings: StandaloneRuntimeSettings

    def run(self) -> None:
        """Run Uvicorn and start post-server plugins after listener readiness."""

        server = self.settings.server
        UvicornRuntimeServer(
            app=self.app,
            runtime=self.runtime,
            settings=UvicornServerSettings(
                host=server.host,
                port=server.port,
                certificate_file=server.ssl_certificate_file,
                private_key_file=server.ssl_private_key_file,
            ),
        ).run()


def create_standalone_app(runtime: AgentRuntime, *, title: str) -> FastAPI:
    """Create a FastAPI app whose lifespan initializes pre-server plugins."""

    return FastAPI(title=title, lifespan=runtime_lifespan(runtime))
