# Scheduler and Retry

## Scheduler

Supported trigger types:

- `startup`;
- `shutdown`;
- `once`;
- `interval`.

Jobs are asynchronous and may be required or optional. Interval jobs require a positive interval. Background loops are canceled before shared resources close because plugins shut down in reverse order.

## Retry

The shared retry policy supports:

- fixed backoff;
- linear backoff;
- exponential backoff;
- maximum delay;
- bounded jitter;
- maximum attempts;
- caller-supplied retryable-exception filtering.

Retry does not make non-idempotent operations safe automatically. Callers must select retry policies based on the operation contract.
