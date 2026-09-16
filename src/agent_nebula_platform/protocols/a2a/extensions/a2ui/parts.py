"""A2UI v1.0 encoding on official A2A 1.x ``Part`` messages.

This module is deliberately transport-binding code. The A2UI domain owns
surfaces and protocol documents; this adapter owns only their representation
using official A2A protobuf types.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct, Value

from a2a.types import Part

from agent_nebula_platform.a2ui.models import (
    A2UIActionRequest,
    A2UI_MIME_TYPE,
    A2UISurface,
)
from agent_nebula_platform.platform.errors import ConfigurationError


def create_a2ui_part(surface: A2UISurface) -> Part:
    """Encode one A2UI surface stream as the v1.0 A2A DataPart representation."""

    messages = [message.copy_document() for message in surface.messages]
    metadata = ParseDict({"mimeType": A2UI_MIME_TYPE}, Struct())
    return Part(data=ParseDict(messages, Value()), metadata=metadata)


def create_a2ui_action_part(action: A2UIActionRequest) -> Part:
    """Encode one renderer-to-agent v1.0 ``action`` in an A2UI A2A DataPart."""

    payload: dict[str, Any] = {
        "name": action.name,
        "surfaceId": action.surface_id,
        "sourceComponentId": action.source_component_id,
        "timestamp": action.timestamp.isoformat().replace("+00:00", "Z"),
        "context": dict(action.context),
    }
    document = {"version": action.version, "action": payload}
    metadata = ParseDict({"mimeType": A2UI_MIME_TYPE}, Struct())
    return Part(data=ParseDict([document], Value()), metadata=metadata)


def parse_a2ui_action_part(part: Part) -> A2UIActionRequest | None:
    """Parse an A2UI renderer ``action`` from an official A2A Part when present."""

    if not part.HasField("data"):
        return None
    metadata = MessageToDict(part.metadata, preserving_proto_field_name=True)
    if metadata.get("mimeType") != A2UI_MIME_TYPE:
        return None
    data = MessageToDict(part.data, preserving_proto_field_name=True)
    if not isinstance(data, list) or len(data) != 1:
        raise ConfigurationError("A2UI action DataPart must contain exactly one message")
    document = data[0]
    if not isinstance(document, Mapping) or document.get("version") != "v1.0":
        raise ConfigurationError("A2UI action DataPart requires a v1.0 message")
    payload = document.get("action")
    if not isinstance(payload, Mapping):
        raise ConfigurationError("A2UI renderer DataPart must contain an action message")
    try:
        return A2UIActionRequest(
            version="v1.0",
            name=payload.get("name"),
            surface_id=payload.get("surfaceId"),
            source_component_id=payload.get("sourceComponentId"),
            timestamp=payload.get("timestamp"),
            context=dict(payload.get("context") or {}),
        )
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("A2UI renderer action is invalid") from exc
