"""Recursive redaction for development protocol traces.

Protocol traces are useful only when they can show message structure.  They must
never become an alternate credential log, so security-bearing keys are removed
before any event reaches Python logging.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_REDACTED = "<redacted>"
_SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
    "dpop",
    "cookie",
    "set-cookie",
    "password",
    "secret",
)


def redact_protocol_value(value: Any) -> Any:
    """Return a JSON-compatible copy with credential-bearing values redacted."""

    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS):
                redacted[str(key)] = _REDACTED
            else:
                redacted[str(key)] = redact_protocol_value(child)
        return redacted
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_protocol_value(child) for child in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
