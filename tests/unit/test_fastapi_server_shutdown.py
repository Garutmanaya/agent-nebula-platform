"""Unit tests for graceful standalone server termination handling."""

from __future__ import annotations

import asyncio
import signal
from typing import Any

from fastapi import FastAPI

from agent_nebula_platform.platform.transport.fastapi.server import (
    UvicornRuntimeServer,
    UvicornServerSettings,
    _capture_shutdown_signals,
    _supported_shutdown_signals,
)


class _Runtime:
    async def initialize_post_server(self) -> None:
        return None


class _SignalServer:
    def __init__(self) -> None:
        self.received: list[tuple[int, Any]] = []

    def handle_exit(self, sig: int, frame: Any) -> None:
        self.received.append((sig, frame))


def _server() -> UvicornRuntimeServer:
    return UvicornRuntimeServer(
        app=FastAPI(),
        runtime=_Runtime(),  # type: ignore[arg-type]
        settings=UvicornServerSettings(host="127.0.0.1", port=8000),
    )


def test_supported_shutdown_signals_include_platform_termination_signals() -> None:
    signals = _supported_shutdown_signals()

    assert signal.SIGINT in signals
    assert signal.SIGTERM in signals
    if hasattr(signal, "SIGHUP"):
        assert signal.SIGHUP in signals
    if hasattr(signal, "SIGQUIT"):
        assert signal.SIGQUIT in signals


def test_signal_capture_installs_and_restores_handlers(monkeypatch: Any) -> None:
    server = _SignalServer()
    installed: dict[signal.Signals, Any] = {}
    original = object()

    def fake_signal(sig: signal.Signals, handler: Any) -> Any:
        previous = installed.get(sig, original)
        installed[sig] = handler
        return previous

    monkeypatch.setattr(signal, "signal", fake_signal)

    with _capture_shutdown_signals(server):
        for shutdown_signal in _supported_shutdown_signals():
            assert installed[shutdown_signal] == server.handle_exit

    for shutdown_signal in _supported_shutdown_signals():
        assert installed[shutdown_signal] is original


def test_run_treats_keyboard_interrupt_as_clean_shutdown(monkeypatch: Any) -> None:
    def interrupt(_coroutine: Any) -> None:
        _coroutine.close()
        raise KeyboardInterrupt

    monkeypatch.setattr(asyncio, "run", interrupt)

    _server().run()
