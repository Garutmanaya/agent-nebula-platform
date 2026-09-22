"""Provider-neutral LLM usage observability built on Platform telemetry and metrics."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from decimal import Decimal

from agent_nebula_platform.platform.metrics import MetricsRegistry
from agent_nebula_platform.platform.telemetry import TelemetryEvent, TelemetryService


@dataclass(frozen=True, slots=True)
class LlmUsageRecord:
    """Represent one provider-reported LLM request usage sample."""

    provider: str
    model: str
    operation: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int
    duration_seconds: float
    estimated_cost_usd: Decimal | None = None


@dataclass(frozen=True, slots=True)
class LlmTokenPricing:
    """USD rates per one million text tokens."""

    input_per_million: Decimal
    cached_input_per_million: Decimal
    output_per_million: Decimal


class LlmCostEstimator:
    """Estimate request cost from an explicit, deliberately small pricing catalog."""

    _PER_MILLION = Decimal(1_000_000)
    _PRICING = {
        # OpenAI published standard text-token rates. Snapshot aliases inherit
        # the base model price by prefix matching below.
        ("openai", "gpt-5-nano"): LlmTokenPricing(
            input_per_million=Decimal("0.05"),
            cached_input_per_million=Decimal("0.005"),
            output_per_million=Decimal("0.40"),
        ),
    }

    def estimate(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        cached_input_tokens: int,
        output_tokens: int,
    ) -> Decimal | None:
        """Return an estimated USD cost, or None when the model is unknown."""

        pricing = self._resolve(provider, model)
        if pricing is None:
            return None
        cached = min(max(cached_input_tokens, 0), max(input_tokens, 0))
        uncached = max(input_tokens - cached, 0)
        cost = (
            Decimal(uncached) * pricing.input_per_million
            + Decimal(cached) * pricing.cached_input_per_million
            + Decimal(max(output_tokens, 0)) * pricing.output_per_million
        ) / self._PER_MILLION
        return cost.quantize(Decimal("0.000000001"))

    def _resolve(self, provider: str, model: str) -> LlmTokenPricing | None:
        provider_key = provider.strip().lower()
        model_key = model.strip().lower()
        exact = self._PRICING.get((provider_key, model_key))
        if exact is not None:
            return exact
        for (known_provider, known_model), pricing in self._PRICING.items():
            if provider_key == known_provider and model_key.startswith(f"{known_model}-"):
                return pricing
        return None


class LlmUsageObserver:
    """Fan one usage record into normal logs, telemetry, and metrics."""

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        telemetry: TelemetryService | None = None,
        metrics: MetricsRegistry | None = None,
        cost_estimator: LlmCostEstimator | None = None,
    ) -> None:
        self._logger = logger or logging.getLogger("agent_nebula_platform.llm")
        self._telemetry = telemetry
        self._metrics = metrics
        self._cost_estimator = cost_estimator or LlmCostEstimator()

    def with_estimated_cost(self, record: LlmUsageRecord) -> LlmUsageRecord:
        """Attach an estimate without changing provider-reported token counts."""

        if record.estimated_cost_usd is not None:
            return record
        estimate = self._cost_estimator.estimate(
            provider=record.provider,
            model=record.model,
            input_tokens=record.input_tokens,
            cached_input_tokens=record.cached_input_tokens,
            output_tokens=record.output_tokens,
        )
        return LlmUsageRecord(
            provider=record.provider,
            model=record.model,
            operation=record.operation,
            input_tokens=record.input_tokens,
            cached_input_tokens=record.cached_input_tokens,
            output_tokens=record.output_tokens,
            reasoning_tokens=record.reasoning_tokens,
            total_tokens=record.total_tokens,
            duration_seconds=record.duration_seconds,
            estimated_cost_usd=estimate,
        )

    async def record(self, record: LlmUsageRecord) -> LlmUsageRecord:
        """Record one usage sample without logging prompts, responses, or secrets."""

        item = self.with_estimated_cost(record)
        cost = "unknown" if item.estimated_cost_usd is None else str(item.estimated_cost_usd)
        self._logger.info(
            "llm.usage | provider=%s model=%s operation=%s input_tokens=%d "
            "cached_input_tokens=%d output_tokens=%d reasoning_tokens=%d "
            "total_tokens=%d estimated_cost_usd=%s duration_ms=%d",
            item.provider,
            item.model,
            item.operation,
            item.input_tokens,
            item.cached_input_tokens,
            item.output_tokens,
            item.reasoning_tokens,
            item.total_tokens,
            cost,
            round(item.duration_seconds * 1000),
        )
        if self._metrics is not None:
            prefix = "llm." + ".".join(
                _metric_dimension(value)
                for value in (item.provider, item.model, item.operation)
            )
            self._metrics.increment(f"{prefix}.requests")
            self._metrics.increment(f"{prefix}.input_tokens", item.input_tokens)
            self._metrics.increment(f"{prefix}.cached_input_tokens", item.cached_input_tokens)
            self._metrics.increment(f"{prefix}.output_tokens", item.output_tokens)
            self._metrics.increment(f"{prefix}.reasoning_tokens", item.reasoning_tokens)
            self._metrics.increment(f"{prefix}.total_tokens", item.total_tokens)
            if item.estimated_cost_usd is not None:
                self._metrics.increment(f"{prefix}.estimated_cost_usd", float(item.estimated_cost_usd))
            self._metrics.observe(f"{prefix}.duration", item.duration_seconds)
        if self._telemetry is not None:
            await self._telemetry.publish(
                TelemetryEvent(
                    event_type="llm.usage",
                    attributes={
                        "provider": item.provider,
                        "model": item.model,
                        "operation": item.operation,
                        "input_tokens": item.input_tokens,
                        "cached_input_tokens": item.cached_input_tokens,
                        "output_tokens": item.output_tokens,
                        "reasoning_tokens": item.reasoning_tokens,
                        "total_tokens": item.total_tokens,
                        "estimated_cost_usd": (
                            str(item.estimated_cost_usd)
                            if item.estimated_cost_usd is not None
                            else None
                        ),
                        "duration_ms": round(item.duration_seconds * 1000),
                    },
                )
            )
        return item


def _metric_dimension(value: str) -> str:
    """Bound a low-cardinality configured dimension for the current registry API."""

    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value.strip().lower())
    return normalized[:100] or "unknown"
