"""A2UI v1.0 encoding on official A2A 1.x ``Part`` messages.

This module is deliberately transport-binding code. The A2UI domain owns
surfaces and protocol documents; this adapter owns only their representation
using official A2A protobuf types.
"""

from __future__ import annotations

from google.protobuf.json_format import ParseDict
from google.protobuf.struct_pb2 import Struct, Value

from a2a.types import Part

from agent_nebula_platform.a2ui.models import A2UI_MIME_TYPE, A2UISurface


def create_a2ui_part(surface: A2UISurface) -> Part:
    """Encode one A2UI surface stream as the v1.0 A2A DataPart representation.

    A2UI v1.0 requires the DataPart payload to be an ordered array of A2UI
    messages and identifies that payload using ``metadata.mimeType``.
    """

    messages = [message.copy_document() for message in surface.messages]
    metadata = ParseDict({"mimeType": A2UI_MIME_TYPE}, Struct())
    return Part(data=ParseDict(messages, Value()), metadata=metadata)
