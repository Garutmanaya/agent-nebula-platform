"""Parse A2UI v1.0 DataParts from normalized official A2A responses."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from agent_nebula_platform.a2ui.models import A2UIDataPart, A2UIMessage, A2UI_MIME_TYPE
from agent_nebula_platform.platform.errors import ConfigurationError


class A2UIResponseParser:
    """Extract and validate A2UI DataParts without changing generic A2A responses."""

    def parse(self, responses: Sequence[Mapping[str, Any]]) -> tuple[A2UIDataPart, ...]:
        result: list[A2UIDataPart] = []
        for response in responses:
            for part in self._parts(response):
                metadata = part.get("metadata")
                if not isinstance(metadata, Mapping):
                    continue
                if metadata.get("mimeType") != A2UI_MIME_TYPE:
                    continue
                data = part.get("data")
                if not isinstance(data, list):
                    raise ConfigurationError("A2UI A2A DataPart data must be an array")
                documents: list[dict[str, Any]] = []
                for document in data:
                    if not isinstance(document, dict):
                        raise ConfigurationError(
                            "A2UI A2A DataPart messages must be JSON objects"
                        )
                    try:
                        message = A2UIMessage(document=document)
                    except ValueError as exc:
                        raise ConfigurationError(
                            "A2UI A2A response contains an invalid v1.0 message"
                        ) from exc
                    documents.append(message.copy_document())
                result.append(
                    A2UIDataPart(data=tuple(documents), metadata=dict(metadata))
                )
        return tuple(result)

    def _parts(self, value: Any):
        if isinstance(value, Mapping):
            parts = value.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    if isinstance(part, Mapping):
                        yield part
            for child in value.values():
                yield from self._parts(child)
        elif isinstance(value, list):
            for child in value:
                yield from self._parts(child)
