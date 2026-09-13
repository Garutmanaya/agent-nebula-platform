"""Immutable event models emitted by A2A protocol observability hooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class A2AProtocolTraceEvent:
    """Describe one logical A2A/A2UI protocol boundary without transport secrets."""

    name: str
    direction: str
    fields: dict[str, Any] = field(default_factory=dict)
