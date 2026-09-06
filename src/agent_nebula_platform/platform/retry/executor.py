"""Asynchronous retry execution with explicit exception classification."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from .policy import RetryPolicy

RetryPredicate = Callable[[Exception], bool]


async def execute_with_retry[T](
    operation: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy,
    retry_if: RetryPredicate | None = None,
    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Execute one asynchronous operation under a bounded retry policy.

    Exceptions are retried only when ``retry_if`` accepts them.  When no
    predicate is supplied, every ordinary ``Exception`` is considered retryable.
    Cancellation is never swallowed because ``CancelledError`` derives from
    ``BaseException`` on supported Python versions.
    """

    policy.validate()
    attempt = 1
    while True:
        try:
            return await operation()
        except Exception as exc:
            if attempt >= policy.max_attempts:
                raise
            if retry_if is not None and not retry_if(exc):
                raise
            await sleeper(policy.delay_for_retry(attempt))
            attempt += 1
