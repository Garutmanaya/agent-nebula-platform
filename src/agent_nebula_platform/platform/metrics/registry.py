"""Thread-safe in-process metrics registry with no exporter dependency."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .models import MetricsSnapshot, TimingSnapshot


@dataclass(slots=True)
class _TimingAccumulator:
    """Mutable internal accumulator hidden behind immutable snapshots."""

    count: int = 0
    total: float = 0.0
    minimum: float | None = None
    maximum: float | None = None


class MetricsRegistry:
    """Collect counters, gauges, and timings for one runtime process."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._timings: dict[str, _TimingAccumulator] = {}

    def increment(self, name: str, value: float = 1.0) -> None:
        """Increment a monotonically increasing counter."""

        _validate_metric_name(name)
        if value < 0:
            raise ValueError("Counter increment cannot be negative")
        with self._lock:
            self._counters[name] = self._counters.get(name, 0.0) + value

    def set_gauge(self, name: str, value: float) -> None:
        """Set the current value of a point-in-time gauge."""

        _validate_metric_name(name)
        with self._lock:
            self._gauges[name] = float(value)

    def observe(self, name: str, duration_seconds: float) -> None:
        """Record one non-negative operation duration."""

        _validate_metric_name(name)
        if duration_seconds < 0:
            raise ValueError("Observed duration cannot be negative")
        with self._lock:
            item = self._timings.setdefault(name, _TimingAccumulator())
            item.count += 1
            item.total += duration_seconds
            item.minimum = (
                duration_seconds
                if item.minimum is None
                else min(item.minimum, duration_seconds)
            )
            item.maximum = (
                duration_seconds
                if item.maximum is None
                else max(item.maximum, duration_seconds)
            )

    def snapshot(self) -> MetricsSnapshot:
        """Return an immutable defensive snapshot suitable for JSON export."""

        with self._lock:
            timings = {
                name: TimingSnapshot(
                    count=value.count,
                    total_seconds=value.total,
                    minimum_seconds=value.minimum,
                    maximum_seconds=value.maximum,
                )
                for name, value in self._timings.items()
            }
            return MetricsSnapshot(
                counters=dict(self._counters),
                gauges=dict(self._gauges),
                timings=timings,
            )


def _validate_metric_name(name: str) -> None:
    """Require stable non-empty metric identifiers."""

    if not name or not name.strip():
        raise ValueError("Metric name cannot be empty")
