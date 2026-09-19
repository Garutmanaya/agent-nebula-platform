"""Typed skill declarations and invocation results."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_nebula_platform.a2ui.models import A2UISurface
from agent_nebula_platform.security.oauth.protected_resource import (
    AuthorizedRequestContext,
)


class SkillInvocation(BaseModel):
    """Carry validated business input and trusted caller context to a skill."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", frozen=True)

    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    security: AuthorizedRequestContext | None = None


class SkillResult(BaseModel):
    """Return transport-neutral structured business output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    ui: A2UISurface | None = None


type SkillHandler = Callable[[SkillInvocation], SkillResult | Awaitable[SkillResult]]


class SkillDefinition(BaseModel):
    """Describe one invokable method and its exact provider-specific scopes."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", frozen=True)

    skill_id: str = Field(min_length=1, max_length=200)
    required_scopes: tuple[str, ...] = ()
    handler: SkillHandler
    description: str | None = None
    schema_contract_id: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
