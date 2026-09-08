"""Typed runtime contracts for declarative A2UI surfaces and actions.

The runtime preserves complete A2UI message documents. It does not render UI,
execute agent-supplied code, or translate component names. Renderer-specific
catalogs and visual styling remain client responsibilities.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

A2UI_MIME_TYPE = "application/a2ui+json"
A2UI_STABLE_VERSION = "v1.0"
A2UI_SUPPORTED_VERSIONS = (A2UI_STABLE_VERSION,)
_AGENT_MESSAGE_KEYS = frozenset(
    {
        "createSurface",
        "updateComponents",
        "updateDataModel",
        "deleteSurface",
        "actionResponse",
        "callFunction",
    }
)


class A2UIMessage(BaseModel):
    """Preserve one complete agent-to-renderer A2UI JSON message."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document: dict[str, Any]

    @field_validator("document")
    @classmethod
    def validate_document_shape(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Require one versioned message without reducing its contents.

        Supported-version policy is applied by :class:`A2UIProtocolPolicy` so
        callers can negotiate future versions without weakening document shape
        validation at the model boundary.
        """

        version = value.get("version")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("A2UI message requires a non-empty version")
        message_keys = _AGENT_MESSAGE_KEYS.intersection(value)
        if len(message_keys) != 1:
            raise ValueError("A2UI message must contain exactly one agent message type")
        allowed_envelope_fields = {"version"}
        message_type = next(iter(message_keys))
        if message_type == "actionResponse":
            allowed_envelope_fields.add("actionId")
        elif message_type == "callFunction":
            allowed_envelope_fields.update({"functionCallId", "wantResponse"})
        unexpected = set(value) - allowed_envelope_fields - message_keys
        if unexpected:
            raise ValueError(
                f"A2UI message contains unsupported top-level fields: {sorted(unexpected)}"
            )
        if message_type == "actionResponse" and not value.get("actionId"):
            raise ValueError("A2UI v1.0 actionResponse requires actionId")
        if message_type == "callFunction" and not value.get("functionCallId"):
            raise ValueError("A2UI v1.0 callFunction requires functionCallId")
        return dict(value)

    @property
    def version(self) -> str:
        """Return the protocol version declared by this message."""

        return str(self.document["version"])

    @property
    def message_type(self) -> str:
        """Return the single protocol message type carried by this document."""

        return next(key for key in _AGENT_MESSAGE_KEYS if key in self.document)

    def copy_document(self) -> dict[str, Any]:
        """Return a defensive deep copy suitable for transport serialization."""

        import copy

        return copy.deepcopy(self.document)


class A2UISurface(BaseModel):
    """Carry a validated sequential A2UI message stream for one surface."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    surface_id: str = Field(min_length=1, max_length=200)
    messages: tuple[A2UIMessage, ...] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2UIDataPart(BaseModel):
    """Represent the A2A DataPart encoding used for A2UI message lists."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["data"] = "data"
    data: tuple[dict[str, Any], ...]
    metadata: dict[str, Any] = Field(
        default_factory=lambda: {"mimeType": A2UI_MIME_TYPE}
    )

    @model_validator(mode="after")
    def validate_mime_type(self) -> A2UIDataPart:
        """Fail closed when the DataPart is not explicitly identified as A2UI."""

        if self.metadata.get("mimeType") != A2UI_MIME_TYPE:
            raise ValueError(f"A2UI DataPart mimeType must be {A2UI_MIME_TYPE}")
        return self


class A2UIActionRequest(BaseModel):
    """Represent one renderer-to-agent action routed to the surface owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(default=A2UI_STABLE_VERSION, min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    surface_id: str = Field(min_length=1, max_length=200)
    source_component_id: str = Field(min_length=1, max_length=200)
    timestamp: datetime
    context: dict[str, Any] = Field(default_factory=dict)
    want_response: bool = False
    action_id: str | None = Field(default=None, min_length=1, max_length=200)
    # Transport-neutral copy of renderer state. A2A carries this separately in
    # a2uiRendererDataModel metadata; it is never serialized inside ``action``.
    data_model: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_response_contract(self) -> A2UIActionRequest:
        """Require the v1.0 action correlation id when a response is requested."""

        if self.want_response and self.action_id is None:
            raise ValueError("A2UI v1.0 actionId is required when wantResponse is true")
        return self


class A2UIActionBinding(BaseModel):
    """Bind one renderer event name to an existing runtime skill."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action_name: str = Field(min_length=1, max_length=200)
    skill_id: str = Field(min_length=1, max_length=200)


class A2UIRendererCapabilities(BaseModel):
    """Describe the A2UI versions and catalog features a renderer accepts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    supported_versions: tuple[str, ...] = Field(min_length=1)
    supported_components: tuple[str, ...] = ()
    supported_functions: tuple[str, ...] = ()


class A2UICapabilities(BaseModel):
    """Expose the runtime's renderer-facing A2UI contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mime_type: Literal["application/a2ui+json"] = A2UI_MIME_TYPE
    supported_versions: tuple[str, ...]
    preferred_version: str
    allowed_components: tuple[str, ...]
    allowed_functions: tuple[str, ...]
    action_names: tuple[str, ...]


class A2UINegotiatedCapabilities(BaseModel):
    """Return the mutually supported A2UI contract for one renderer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mime_type: Literal["application/a2ui+json"] = A2UI_MIME_TYPE
    version: str
    components: tuple[str, ...]
    functions: tuple[str, ...]
