"""Request-scoped execution correlation for safe, structured observability.

This module is intentionally transport-neutral. Runtime components emit only
sanitized metadata through :func:`record_execution_event`; hosts such as Nebula
Explorer decide how those events are stored or rendered. The execution trace is
therefore pluggable without coupling Runtime to any UI or persistence backend.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

EXECUTION_ID_HEADER = "X-Agent-Nebula-Execution-Id"
SECURITY_TRACE_HEADER = "X-Agent-Nebula-Security-Trace"

# Security artifacts must never cross the Runtime trace boundary. Keeping the
# list here protects every recorder, including future hosts that do not apply a
# second layer of redaction.
_SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "client_assertion",
    "client_secret",
    "cookie",
    "dpop",
    "password",
    "private_key",
    "refresh_token",
    "set_cookie",
}
_MAX_STRING_LENGTH = 1024
_MAX_SEQUENCE_ITEMS = 32
_MAX_MAPPING_ITEMS = 64
_MAX_DEPTH = 6


@dataclass(frozen=True, slots=True)
class ExecutionTraceContext:
    """Carry one correlation identifier and optional semantic event callback."""

    execution_id: str
    recorder: Callable[[dict[str, Any]], None] | None = None


_current: ContextVar[ExecutionTraceContext | None] = ContextVar(
    "agent_nebula_platform_execution_trace", default=None
)


def activate_execution_trace(
    execution_id: str,
    *,
    recorder: Callable[[dict[str, Any]], None] | None = None,
) -> Token:
    """Bind one execution identifier to nested Runtime HTTP operations."""

    return _current.set(
        ExecutionTraceContext(execution_id=execution_id, recorder=recorder)
    )


def reset_execution_trace(token: Token) -> None:
    """Restore the previous execution-trace context."""

    _current.reset(token)


def current_execution_trace() -> ExecutionTraceContext | None:
    """Return the active execution-trace context, if one exists."""

    return _current.get()


def execution_headers() -> dict[str, str]:
    """Return safe correlation headers for one outbound request."""

    context = current_execution_trace()
    return {EXECUTION_ID_HEADER: context.execution_id} if context else {}


def record_execution_event(event: Mapping[str, Any]) -> None:
    """Publish one sanitized event to the active host trace.

    Runtime owns the first redaction boundary because OAuth/DPoP components are
    closest to security artifacts. Explorer and other hosts may apply stricter
    redaction, but they must never receive raw tokens, assertions, proofs, keys,
    passwords, or authorization headers from Runtime.
    """

    context = current_execution_trace()
    if context and context.recorder:
        sanitized = _sanitize_trace_value(dict(event))
        if isinstance(sanitized, dict):
            context.recorder(sanitized)


def _sanitize_trace_value(value: Any, *, depth: int = 0) -> Any:
    """Return a bounded JSON-safe trace value with sensitive fields removed."""

    if depth >= _MAX_DEPTH:
        return "<max-depth>"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (key, nested) in enumerate(value.items()):
            if index >= _MAX_MAPPING_ITEMS:
                result["<truncated>"] = True
                break
            text_key = str(key)
            normalized = text_key.lower().replace("-", "_")
            result[text_key] = (
                "<redacted>"
                if normalized in _SENSITIVE_KEYS
                else _sanitize_trace_value(nested, depth=depth + 1)
            )
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = [
            _sanitize_trace_value(item, depth=depth + 1)
            for item in value[:_MAX_SEQUENCE_ITEMS]
        ]
        if len(value) > _MAX_SEQUENCE_ITEMS:
            items.append("<truncated>")
        return items
    if isinstance(value, (bytes, bytearray)):
        return f"<binary:{len(value)}>"
    if isinstance(value, str):
        return (
            value
            if len(value) <= _MAX_STRING_LENGTH
            else f"{value[:_MAX_STRING_LENGTH]}…"
        )
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)
