"""Metrics exporter contracts and the built-in JSON-compatible exporter."""

from __future__ import annotations

from typing import Protocol

from .models import MetricsSnapshot


class MetricsExporter(Protocol):
    """Export one immutable metrics snapshot."""

    async def export(self, snapshot: MetricsSnapshot) -> None:
        """Publish the supplied snapshot to an external destination."""


class NullMetricsExporter:
    """Discard snapshots when no external metrics backend is configured."""

    async def export(self, snapshot: MetricsSnapshot) -> None:
        """Discard the supplied snapshot."""

        del snapshot
