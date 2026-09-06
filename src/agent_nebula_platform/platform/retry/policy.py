"""Retry policy models shared by runtime integrations and background jobs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from random import Random


class BackoffStrategy(StrEnum):
    """Supported delay strategies for retry execution."""

    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Define bounded retry behavior without prescribing a transport."""

    max_attempts: int = 3
    initial_delay_seconds: float = 0.25
    maximum_delay_seconds: float = 30.0
    multiplier: float = 2.0
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    jitter_ratio: float = 0.1

    def validate(self) -> None:
        """Reject unsafe or nonsensical retry settings before execution."""

        if self.max_attempts < 1:
            raise ValueError("Retry max_attempts must be at least one")
        if self.initial_delay_seconds < 0:
            raise ValueError("Retry initial delay cannot be negative")
        if self.maximum_delay_seconds < self.initial_delay_seconds:
            raise ValueError("Retry maximum delay cannot be below initial delay")
        if self.multiplier < 1:
            raise ValueError("Retry multiplier must be at least one")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("Retry jitter ratio must be between zero and one")

    def delay_for_retry(
        self, retry_number: int, *, random: Random | None = None
    ) -> float:
        """Return the delay before the requested retry number.

        ``retry_number`` starts at one for the delay before the second attempt.
        Jitter is bounded symmetrically so delays never become negative.
        """

        self.validate()
        if retry_number < 1:
            raise ValueError("Retry number must be at least one")
        if self.strategy is BackoffStrategy.FIXED:
            base = self.initial_delay_seconds
        elif self.strategy is BackoffStrategy.LINEAR:
            base = self.initial_delay_seconds * retry_number
        else:
            base = self.initial_delay_seconds * (self.multiplier ** (retry_number - 1))
        bounded = min(base, self.maximum_delay_seconds)
        if self.jitter_ratio == 0 or bounded == 0:
            return bounded
        generator = random or Random()
        spread = bounded * self.jitter_ratio
        return max(0.0, bounded + generator.uniform(-spread, spread))
