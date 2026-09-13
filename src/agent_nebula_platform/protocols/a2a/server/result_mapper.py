"""Map transport-neutral business results to official A2A response messages."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct, Value

from a2a.types import Message, Part, Role

from agent_nebula_platform.a2ui.models import A2UISurface
from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.protocols.a2a.extensions.a2ui.parts import create_a2ui_part
from agent_nebula_platform.protocols.a2a.extensions.a2ui.observability import summarize_a2ui_parts
from agent_nebula_platform.protocols.a2a.observability import A2AProtocolTraceEvent, A2AProtocolTracer
from agent_nebula_platform.protocols.a2a.observability.tracer import create_protocol_tracer_from_environment
from agent_nebula_platform.skills import SkillResult


class A2AResultMapper:
    """Convert business results without putting extension logic in the executor.

    Structured business data remains a normal A2A DataPart. A2UI presentation
    is delegated to the isolated A2UI/A2A binding and becomes an additional
    DataPart. The mapper does not interpret A2UI documents or configuration.
    """

    def __init__(self, *, protocol_tracer: A2AProtocolTracer | None = None) -> None:
        """Create a result mapper with an independently replaceable protocol tracer."""

        self._protocol_tracer = protocol_tracer or create_protocol_tracer_from_environment()

    def map(self, result: Mapping[str, object] | SkillResult) -> Message:
        """Return one official A2A agent message preserving all result channels."""

        data, metadata, ui = self._normalize(result)
        parts: list[Part] = []

        text = self._conventional_text(data)
        if text is not None:
            # Retain the conventional human-readable projection for existing
            # generic A2A clients while also preserving the complete data below.
            parts.append(Part(text=text))
        if data:
            parts.append(Part(data=ParseDict(data, Value())))
        if ui is not None:
            parts.append(create_a2ui_part(ui))

        if not parts:
            raise ConfigurationError("A2A skill result must contain data or A2UI output")

        arguments: dict[str, Any] = {
            "message_id": str(uuid4()),
            "role": Role.ROLE_AGENT,
            "parts": parts,
        }
        if metadata:
            arguments["metadata"] = ParseDict(metadata, Struct())
        message = Message(**arguments)
        self._trace_mapped_response(message, part_count=len(parts))
        return message

    def _trace_mapped_response(self, message: Message, *, part_count: int) -> None:
        """Trace a mapped response without affecting the returned A2A message."""

        try:
            document = MessageToDict(message, preserving_proto_field_name=True)
            fields: dict[str, Any] = {
                "messageId": (
                    document.get("message_id") or document.get("messageId")
                ),
                "partCount": part_count,
            }
            a2ui_parts = summarize_a2ui_parts(document)
            if a2ui_parts:
                fields["a2uiParts"] = a2ui_parts
            if self._protocol_tracer.include_payloads:
                fields["message"] = document
            self._protocol_tracer.emit(
                A2AProtocolTraceEvent("response.map", "server->remote", fields)
            )
        except Exception:  # noqa: BLE001 - tracing must never break response mapping.
            return

    @staticmethod
    def _normalize(
        result: Mapping[str, object] | SkillResult,
    ) -> tuple[dict[str, Any], dict[str, Any], A2UISurface | None]:
        if isinstance(result, SkillResult):
            return dict(result.data), dict(result.metadata), result.ui
        if isinstance(result, Mapping):
            return dict(result), {}, None
        raise ConfigurationError("A2A skill result must be a mapping or SkillResult")

    @staticmethod
    def _conventional_text(data: Mapping[str, object]) -> str | None:
        for key in ("message", "text"):
            value = data.get(key)
            if value is not None:
                return str(value)
        return None
