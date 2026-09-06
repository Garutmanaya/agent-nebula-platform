"""Public API contract tests for Runtime Checkpoint 9."""

from agent_nebula_platform import (
    JobTriggerType,
    MetricsRegistry,
    RuntimeHealthService,
    RuntimeScheduler,
    ScheduledJob,
    TelemetryEvent,
    TelemetryService,
)
from agent_nebula_platform.platform.capabilities import (
    RuntimeCapability,
    require_available,
)
from agent_nebula_platform.platform.retry import RetryPolicy, execute_with_retry


def test_checkpoint9_public_symbols_are_importable() -> None:
    """Operational runtime APIs remain available from documented packages."""

    assert MetricsRegistry is not None
    assert RuntimeHealthService is not None
    assert RuntimeScheduler is not None
    assert ScheduledJob is not None
    assert JobTriggerType is not None
    assert TelemetryEvent is not None
    assert TelemetryService is not None
    assert RetryPolicy is not None
    assert execute_with_retry is not None


def test_checkpoint9_capabilities_are_available() -> None:
    """Metrics, telemetry, and scheduler are no longer roadmap placeholders."""

    assert require_available(RuntimeCapability.METRICS).checkpoint == "9"
    assert require_available(RuntimeCapability.TELEMETRY).checkpoint == "9"
    assert require_available(RuntimeCapability.SCHEDULER).checkpoint == "9"
