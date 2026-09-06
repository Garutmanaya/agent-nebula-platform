"""Shared dependency context supplied to runtime plugins."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_nebula_platform.integrations.nebula.connector import NebulaConnector

from .events import EventSink
from .services import RuntimeServiceRegistry
from .state import RuntimeStateStore


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    """Caller-composed runtime dependencies available to every plugin."""

    nebula: NebulaConnector
    state_store: RuntimeStateStore
    events: EventSink
    services: RuntimeServiceRegistry = field(default_factory=RuntimeServiceRegistry)
