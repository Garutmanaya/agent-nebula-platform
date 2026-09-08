"""Declarative A2UI surface validation and secure action dispatch.

The service export is resolved lazily to avoid a package-initialization cycle
between typed skill results and A2UI action dispatch.
"""

from __future__ import annotations

from typing import Any

from .actions import A2UIActionDispatcher
from .configuration import A2UIConfiguration
from .data_model import A2UIDataModelService
from .events import A2UISessionEvent
from .models import (
    A2UI_MIME_TYPE,
    A2UI_STABLE_VERSION,
    A2UI_SUPPORTED_VERSIONS,
    A2UIActionBinding,
    A2UIActionRequest,
    A2UICapabilities,
    A2UIDataPart,
    A2UIMessage,
    A2UINegotiatedCapabilities,
    A2UIRendererCapabilities,
    A2UISurface,
)
from .session import (
    A2UIActionRecord,
    A2UISessionService,
    A2UISessionSnapshot,
    A2UISessionStatus,
    A2UISurfaceFrame,
    A2UISurfaceMode,
    A2UITaskReference,
    JsonFileA2UISessionStore,
    MemoryA2UISessionStore,
)
from .surfaces import A2UISurfaceManager, SurfaceStackResult
from .validation import A2UIComponentPolicy, A2UIProtocolPolicy

__all__ = [
    "A2UI_MIME_TYPE",
    "A2UI_STABLE_VERSION",
    "A2UI_SUPPORTED_VERSIONS",
    "A2UIActionBinding",
    "A2UIActionDispatcher",
    "A2UIActionRecord",
    "A2UIActionRequest",
    "A2UICapabilities",
    "A2UIComponentPolicy",
    "A2UIConfiguration",
    "A2UIDataModelService",
    "A2UIDataPart",
    "A2UIMessage",
    "A2UINegotiatedCapabilities",
    "A2UIProtocolPolicy",
    "A2UIRendererCapabilities",
    "A2UIService",
    "A2UISessionEvent",
    "A2UISessionService",
    "A2UISessionSnapshot",
    "A2UISessionStatus",
    "A2UISurface",
    "A2UISurfaceFrame",
    "A2UISurfaceManager",
    "A2UISurfaceMode",
    "A2UITaskReference",
    "JsonFileA2UISessionStore",
    "MemoryA2UISessionStore",
    "SurfaceStackResult",
]


def __getattr__(name: str) -> Any:
    """Resolve the A2UI service only when callers explicitly request it."""

    if name == "A2UIService":
        from .service import A2UIService

        return A2UIService
    raise AttributeError(name)
