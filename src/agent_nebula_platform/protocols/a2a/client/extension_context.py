"""Composable client-side A2A extension request context.

This module is transport-neutral within the A2A binding. Individual extensions
contribute activation URIs, request/message metadata, and call state without
teaching :class:`A2AClientAdapter` extension-specific wire semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from a2a.client import ClientCallContext
from a2a.client.service_parameters import ServiceParametersFactory, with_a2a_extensions
from a2a.types import AgentCard
from google.protobuf.json_format import ParseDict
from google.protobuf.struct_pb2 import Struct

from agent_nebula_platform.platform.errors import ConfigurationError


@dataclass(frozen=True)
class A2AClientExtensionContribution:
    """One extension's contribution to an outgoing A2A call."""

    extension_uris: tuple[str, ...] = ()
    state: dict[str, Any] = field(default_factory=dict)
    request_metadata: dict[str, Any] = field(default_factory=dict)
    message_metadata: dict[str, Any] = field(default_factory=dict)


class A2AClientExtension(Protocol):
    """Contract implemented by independently replaceable client extensions."""

    def prepare(
        self, agent_card: AgentCard, *, skill_id: str | None
    ) -> A2AClientExtensionContribution:
        """Return this extension's contribution for one call."""


@dataclass(frozen=True)
class A2AClientExtensionContext:
    """Merged extension state for one official A2A client invocation."""

    call_context: ClientCallContext | None
    request_metadata: Struct | None
    message_metadata: Struct | None


class A2AClientExtensionContextBuilder:
    """Merge independent A2A extensions into one official call context."""

    def __init__(self, extensions: tuple[A2AClientExtension, ...] = ()) -> None:
        self._extensions = extensions

    def build(
        self, agent_card: AgentCard, *, skill_id: str | None = None
    ) -> A2AClientExtensionContext:
        uris: list[str] = []
        state: dict[str, Any] = {}
        request_metadata: dict[str, Any] = {}
        message_metadata: dict[str, Any] = {}

        for extension in self._extensions:
            contribution = extension.prepare(agent_card, skill_id=skill_id)
            for uri in contribution.extension_uris:
                if uri not in uris:
                    uris.append(uri)
            self._merge_unique(state, contribution.state, "call state")
            self._merge_unique(
                request_metadata, contribution.request_metadata, "request metadata"
            )
            self._merge_unique(
                message_metadata, contribution.message_metadata, "message metadata"
            )

        context = None
        if uris or state:
            context = ClientCallContext(
                state=state,
                service_parameters=(
                    ServiceParametersFactory.create([with_a2a_extensions(uris)])
                    if uris
                    else None
                ),
            )
        return A2AClientExtensionContext(
            call_context=context,
            request_metadata=self._as_struct(request_metadata),
            message_metadata=self._as_struct(message_metadata),
        )

    @staticmethod
    def _merge_unique(target: dict[str, Any], source: dict[str, Any], label: str) -> None:
        overlap = set(target).intersection(source)
        if overlap:
            raise ConfigurationError(
                f"A2A extensions produced conflicting {label}",
                details={"keys": sorted(overlap)},
            )
        target.update(source)

    @staticmethod
    def _as_struct(value: dict[str, Any]) -> Struct | None:
        return ParseDict(value, Struct()) if value else None
