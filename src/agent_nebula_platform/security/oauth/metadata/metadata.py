"""Authoritative OAuth Protected Resource Metadata document contracts."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class ProtectedResourceMetadataDocument(BaseModel):
    """Preserve one complete RFC 9728 metadata document without reconstruction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        document: Mapping[str, Any],
    ) -> ProtectedResourceMetadataDocument:
        """Create an immutable wrapper around complete authoritative metadata."""

        return cls(document=deepcopy(dict(document)))

    def copy_document(self) -> dict[str, Any]:
        """Return a defensive copy suitable for an HTTP response."""

        return deepcopy(self.document)


class ProtectedResourceMetadataProvider(Protocol):
    """Supply authoritative protected-resource metadata owned by the host."""

    def get_protected_resource_metadata(self) -> ProtectedResourceMetadataDocument:
        """Return the current complete metadata document."""


class StaticProtectedResourceMetadataProvider:
    """Expose immutable metadata supplied during composition."""

    def __init__(self, document: Mapping[str, Any]) -> None:
        self._document = ProtectedResourceMetadataDocument(
            document=deepcopy(dict(document))
        )

    def get_protected_resource_metadata(self) -> ProtectedResourceMetadataDocument:
        """Return the configured metadata document."""

        return self._document
