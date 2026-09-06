"""Surface-stack policy helpers used by the A2UI session engine."""

from __future__ import annotations

from agent_nebula_platform.a2ui.session.models import A2UISurfaceFrame, A2UISurfaceMode

from .models import SurfaceStackResult


class A2UISurfaceManager:
    """Apply push, replace, append, and history-truncation semantics."""

    def __init__(self, max_history: int = 50) -> None:
        """Set the bounded retained surface count."""

        self._max_history = max_history

    def apply(
        self,
        surfaces: tuple[A2UISurfaceFrame, ...],
        cursor: int,
        frame: A2UISurfaceFrame,
    ) -> SurfaceStackResult:
        """Apply one deterministic surface transition."""

        items = list(surfaces)
        if frame.mode == A2UISurfaceMode.REPLACE and cursor >= 0:
            items[cursor] = frame
        elif frame.mode == A2UISurfaceMode.APPEND and cursor >= 0:
            current = items[cursor]
            items[cursor] = current.model_copy(
                update={
                    "messages": (*current.messages, *frame.messages),
                    "data": {**current.data, **frame.data},
                    "metadata": {
                        **current.metadata,
                        **frame.metadata,
                    },
                }
            )
        else:
            if cursor < len(items) - 1:
                items = items[: cursor + 1]
            items.append(frame)
            cursor = len(items) - 1

        if len(items) > self._max_history:
            overflow = len(items) - self._max_history
            items = items[overflow:]
            cursor = max(-1, cursor - overflow)

        return SurfaceStackResult(
            surfaces=tuple(items),
            cursor=cursor,
        )
