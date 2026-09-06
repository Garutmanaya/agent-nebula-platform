"""Uvicorn server ownership with an explicit listener-ready lifecycle boundary."""

from __future__ import annotations

import asyncio
import signal
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

from agent_nebula_platform.platform.errors import PluginError

if TYPE_CHECKING:
    from agent_nebula_platform.platform.runtime import AgentRuntime


def _supported_shutdown_signals() -> tuple[signal.Signals, ...]:
    """Return catchable process signals that request an orderly service shutdown.

    SIGKILL and SIGSTOP are intentionally absent because operating systems do not
    allow applications to catch or defer them.
    """

    signal_names = ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT", "SIGBREAK")
    supported: list[signal.Signals] = []
    for name in signal_names:
        value = getattr(signal, name, None)
        if value is not None and value not in supported:
            supported.append(value)
    return tuple(supported)


@contextmanager
def _capture_shutdown_signals(server: Any) -> Iterator[None]:
    """Translate catchable termination signals into Uvicorn shutdown requests.

    Uvicorn normally re-raises captured signals after its graceful shutdown
    finishes. That behavior is useful for command-line process semantics, but it
    produces a misleading ``KeyboardInterrupt`` traceback for Agent Runtime even
    after FastAPI lifespan cleanup completed successfully.

    Agent Runtime owns the process lifecycle, so it captures the same termination
    intent plus the conventional Unix HUP/QUIT signals, lets Uvicorn complete its
    lifespan shutdown, restores the previous handlers, and does not re-raise the
    signal afterward.
    """

    if threading.current_thread() is not threading.main_thread():
        yield
        return

    original_handlers = {
        shutdown_signal: signal.signal(shutdown_signal, server.handle_exit)
        for shutdown_signal in _supported_shutdown_signals()
    }
    try:
        yield
    finally:
        for shutdown_signal, original_handler in original_handlers.items():
            signal.signal(shutdown_signal, original_handler)


@dataclass(frozen=True, slots=True)
class UvicornServerSettings:
    """Describe the network and TLS settings for one standalone ASGI listener."""

    host: str
    port: int
    certificate_file: Path | None = None
    private_key_file: Path | None = None
    readiness_timeout_seconds: float = 30.0


class UvicornRuntimeServer:
    """Start Uvicorn, then initialize callback-dependent runtime plugins."""

    def __init__(
        self,
        *,
        app: FastAPI,
        runtime: AgentRuntime,
        settings: UvicornServerSettings,
    ) -> None:
        self._app = app
        self._runtime = runtime
        self._settings = settings

    def run(self) -> None:
        """Run the listener until completion or an orderly process shutdown.

        SIGINT, SIGTERM, SIGHUP, SIGQUIT, and SIGBREAK (where supported) are
        treated as expected operator/platform shutdown requests. FastAPI lifespan
        cleanup completes before this method returns, and no termination
        traceback is emitted. SIGKILL and SIGSTOP cannot be caught by a process.
        """

        try:
            asyncio.run(self.serve())
        except KeyboardInterrupt:
            # Defensive fallback for Python/ASGI server implementations that may
            # still surface SIGINT after their graceful shutdown path completes.
            return

    async def serve(self) -> None:
        """Wait for the listener before starting post-server plugins."""

        try:
            import uvicorn
        except ImportError as exc:  # pragma: no cover - packaging guard
            raise RuntimeError(
                "Uvicorn server support requires the 'standalone' package extra"
            ) from exc

        tls_options: dict[str, str] = {}
        if self._settings.certificate_file is not None:
            tls_options["ssl_certfile"] = str(self._settings.certificate_file)
        if self._settings.private_key_file is not None:
            tls_options["ssl_keyfile"] = str(self._settings.private_key_file)

        config = uvicorn.Config(
            self._app,
            host=self._settings.host,
            port=self._settings.port,
            **tls_options,
        )

        class GracefulUvicornServer(uvicorn.Server):
            """Uvicorn server variant that does not re-raise handled shutdown signals."""

            @contextmanager
            def capture_signals(self) -> Iterator[None]:
                with _capture_shutdown_signals(self):
                    yield

        server = GracefulUvicornServer(config)
        serve_task = asyncio.create_task(server.serve())
        try:
            await self._wait_until_started(server, serve_task)
            await self._runtime.initialize_post_server()
            await serve_task
        except BaseException:
            server.should_exit = True
            if not serve_task.done():
                await serve_task
            raise

    async def _wait_until_started(
        self, server: object, serve_task: asyncio.Task[None]
    ) -> None:
        """Wait until Uvicorn reports a listening server or fails early."""

        deadline = (
            asyncio.get_running_loop().time() + self._settings.readiness_timeout_seconds
        )
        while not bool(getattr(server, "started", False)):
            if serve_task.done():
                exception = serve_task.exception()
                if exception is not None:
                    raise exception
                raise PluginError("Uvicorn stopped before reporting listener readiness")
            if asyncio.get_running_loop().time() >= deadline:
                raise PluginError("Uvicorn listener readiness timed out")
            await asyncio.sleep(0.02)
