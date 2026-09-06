"""Deterministic synchronized A2UI data-model operations."""

from __future__ import annotations

from typing import Any


class A2UIDataModelService:
    """Apply immutable deep-merge updates without interpreting domain fields."""

    def merge(
        self,
        current: dict[str, Any],
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a recursively merged copy of the current data model."""

        result = dict(current)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self.merge(result[key], value)
            else:
                result[key] = value
        return result
