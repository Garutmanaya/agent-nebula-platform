from decimal import Decimal

import pytest

from agent_nebula_platform.platform.llm import LlmCostEstimator, LlmUsageObserver, LlmUsageRecord
from agent_nebula_platform.platform.metrics import MetricsRegistry


def test_gpt_5_nano_cost_accounts_for_cached_input() -> None:
    estimate = LlmCostEstimator().estimate(
        provider="openai", model="gpt-5-nano", input_tokens=2000,
        cached_input_tokens=1000, output_tokens=500,
    )
    assert estimate == Decimal("0.000255000")


def test_unknown_model_has_no_estimated_cost() -> None:
    assert LlmCostEstimator().estimate(
        provider="other", model="unknown", input_tokens=1,
        cached_input_tokens=0, output_tokens=1,
    ) is None


@pytest.mark.asyncio
async def test_observer_records_metrics() -> None:
    metrics = MetricsRegistry()
    observer = LlmUsageObserver(metrics=metrics)
    await observer.record(LlmUsageRecord(
        provider="openai", model="gpt-5-nano", operation="orchestrator.plan",
        input_tokens=10, cached_input_tokens=2, output_tokens=3,
        reasoning_tokens=1, total_tokens=13, duration_seconds=0.25,
    ))
    snapshot = metrics.snapshot()
    prefix = "llm.openai.gpt-5-nano.orchestrator.plan"
    assert snapshot.counters[f"{prefix}.requests"] == 1
    assert snapshot.counters[f"{prefix}.total_tokens"] == 13
    assert snapshot.timings[f"{prefix}.duration"].count == 1
