"""A2UI-specific inspection helpers for A2A protocol traces.

This module understands only the A2UI-over-A2A representation.  The generic A2A
tracer therefore remains independent from A2UI while still being able to emit a
useful negotiation and DataPart summary through this extension-owned adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .extension import A2UI_EXTENSION_URI

_RENDERER_CAPABILITY_KEYS = ("a2uiRendererCapabilities", "a2uiClientCapabilities")


def summarize_a2ui_agent_card(card: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return the advertised A2UI extension contract from a normalized Agent Card."""

    capabilities = card.get("capabilities")
    if not isinstance(capabilities, Mapping):
        return None
    extensions = capabilities.get("extensions")
    if not isinstance(extensions, list):
        return None
    for extension in extensions:
        if isinstance(extension, Mapping) and extension.get("uri") == A2UI_EXTENSION_URI:
            return {
                "uri": A2UI_EXTENSION_URI,
                "params": extension.get("params", {}),
            }
    return None


def summarize_a2ui_message_metadata(metadata: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return renderer capability/data-model metadata carried by one A2A Message."""

    summary: dict[str, Any] = {}
    for key in _RENDERER_CAPABILITY_KEYS:
        value = metadata.get(key)
        if value is not None:
            summary[key] = value
    if "a2uiRendererDataModel" in metadata:
        summary["a2uiRendererDataModel"] = metadata["a2uiRendererDataModel"]
    return summary or None


def summarize_a2ui_parts(document: Any) -> tuple[dict[str, Any], ...]:
    """Find normalized A2UI DataParts and summarize their v1.0 message envelopes."""

    summaries: list[dict[str, Any]] = []
    _collect_parts(document, summaries)
    return tuple(summaries)


def _collect_parts(value: Any, summaries: list[dict[str, Any]]) -> None:
    """Recursively inspect normalized A2A documents for A2UI DataParts."""

    if isinstance(value, Mapping):
        parts = value.get("parts")
        if isinstance(parts, list):
            for part in parts:
                if not isinstance(part, Mapping):
                    continue
                metadata = part.get("metadata")
                if not isinstance(metadata, Mapping) or metadata.get("mimeType") != "application/a2ui+json":
                    continue
                data = part.get("data")
                messages: list[dict[str, Any]] = []
                if isinstance(data, list):
                    for item in data:
                        if not isinstance(item, Mapping):
                            continue
                        message_type = next((key for key in item if key != "version"), "unknown")
                        payload = item.get(message_type)
                        entry: dict[str, Any] = {
                            "version": item.get("version"),
                            "messageType": message_type,
                        }
                        if isinstance(payload, Mapping):
                            for key in ("surfaceId", "catalogId", "actionId", "name"):
                                if key in payload:
                                    entry[key] = payload[key]
                            components = payload.get("components")
                            if isinstance(components, list):
                                entry["componentCount"] = len(components)
                        messages.append(entry)
                summaries.append({"mimeType": metadata.get("mimeType"), "messages": messages})
        for child in value.values():
            _collect_parts(child, summaries)
    elif isinstance(value, list):
        for child in value:
            _collect_parts(child, summaries)
