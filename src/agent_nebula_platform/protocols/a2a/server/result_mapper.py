"""Map transport-neutral business results to official A2A response messages."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from google.protobuf.json_format import ParseDict
from google.protobuf.struct_pb2 import Struct, Value

from a2a.types import Message, Part, Role

from agent_nebula_platform.a2ui.models import A2UISurface
from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.protocols.a2a.extensions.a2ui.parts import create_a2ui_part
from agent_nebula_platform.skills import SkillResult


class A2AResultMapper:
    """Convert business results without putting extension logic in the executor.

    Structured business data remains a normal A2A DataPart. A2UI presentation
    is delegated to the isolated A2UI/A2A binding and becomes an additional
    DataPart. The mapper does not interpret A2UI documents or configuration.
    """

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
        return Message(**arguments)

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
