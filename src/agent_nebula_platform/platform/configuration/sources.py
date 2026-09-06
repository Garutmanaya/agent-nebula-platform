"""Configuration-source parsing and deterministic precedence utilities.

This module contains only source-neutral mapping operations.  It does not know
about standalone preset models, which keeps the same precedence machinery
usable by embedded hosts and future language-specific adapters.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, MutableMapping, Sequence
from copy import deepcopy
from typing import Any

from agent_nebula_platform.platform.errors import ConfigurationError


def merge_mappings(*layers: Mapping[str, Any]) -> dict[str, Any]:
    """Merge configuration layers from lowest to highest precedence.

    Nested mappings are merged recursively.  Scalar values and sequences are
    replaced as complete values because partially merging security-sensitive
    configuration would make the effective configuration difficult to audit.
    """

    result: dict[str, Any] = {}
    for layer in layers:
        _merge_into(result, layer)
    return result


def environment_overrides(
    environment: Mapping[str, str],
    *,
    prefix: str = "AGENT_RUNTIME__",
) -> dict[str, Any]:
    """Convert double-underscore environment variables into nested settings.

    For example, ``AGENT_RUNTIME__SERVER__PORT=8443`` becomes
    ``{"server": {"port": 8443}}``.  ``AGENT_RUNTIME_HOME`` is intentionally
    excluded because it defines the external product root rather than a model
    field override.
    """

    overrides: dict[str, Any] = {}
    for name, raw_value in environment.items():
        if not name.startswith(prefix):
            continue
        suffix = name[len(prefix) :].strip("_")
        if not suffix:
            continue
        path = tuple(part.lower() for part in suffix.split("__") if part)
        if not path:
            continue
        set_dotted_value(overrides, path, parse_scalar(raw_value))
    return overrides


def cli_overrides(values: Mapping[str, Any] | Sequence[str] | None) -> dict[str, Any]:
    """Convert caller-provided CLI overrides into a nested mapping.

    Callers may pass a mapping whose keys use dotted paths or a sequence of
    ``key=value`` strings.  Parsing command-line arguments remains the host
    application's responsibility; this function only normalizes explicit
    overrides supplied to Agent Runtime.
    """

    if values is None:
        return {}
    items: list[tuple[str, Any]] = []
    if isinstance(values, Mapping):
        items.extend((str(key), value) for key, value in values.items())
    else:
        for item in values:
            key, separator, raw_value = item.partition("=")
            if not separator or not key.strip():
                raise ConfigurationError(
                    "CLI override must use key=value syntax",
                    details={"override": item},
                )
            items.append((key, parse_scalar(raw_value)))

    overrides: dict[str, Any] = {}
    for key, value in items:
        path = tuple(part.strip().lower() for part in key.split(".") if part.strip())
        if not path:
            raise ConfigurationError("CLI override contains an empty key")
        set_dotted_value(overrides, path, value)
    return overrides


def parse_scalar(value: str) -> Any:
    """Parse common JSON scalar and collection values without guessing paths.

    Strings that are not valid JSON remain strings.  This allows URLs and file
    references to pass through unchanged while preserving booleans, numbers,
    arrays, objects, and null values when explicitly provided.
    """

    stripped = value.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return stripped


def set_dotted_value(
    target: MutableMapping[str, Any],
    path: Sequence[str],
    value: Any,
) -> None:
    """Set one nested value while rejecting scalar-to-object collisions."""

    current: MutableMapping[str, Any] = target
    for part in path[:-1]:
        existing = current.get(part)
        if existing is None:
            nested: dict[str, Any] = {}
            current[part] = nested
            current = nested
            continue
        if not isinstance(existing, MutableMapping):
            raise ConfigurationError(
                "Configuration override collides with a scalar value",
                details={"path": ".".join(path)},
            )
        current = existing
    current[path[-1]] = value


def _merge_into(target: MutableMapping[str, Any], layer: Mapping[str, Any]) -> None:
    """Recursively merge one layer into an existing mutable mapping."""

    for key, value in layer.items():
        existing = target.get(key)
        if isinstance(existing, MutableMapping) and isinstance(value, Mapping):
            _merge_into(existing, value)
        else:
            target[key] = deepcopy(value)
