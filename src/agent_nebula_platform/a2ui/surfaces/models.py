"""Surface-stack transition models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from agent_nebula_platform.a2ui.session.models import A2UISurfaceFrame


class SurfaceStackResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    surfaces: tuple[A2UISurfaceFrame, ...]
    cursor: int
