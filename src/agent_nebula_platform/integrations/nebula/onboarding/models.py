"""Runtime-facing onboarding configuration and cached result models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OnboardingSettings(BaseModel):
    """Retry and state policy for one Agent Nebula onboarding operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True
    state_key: str = Field(default="onboarding", min_length=1)
    retry_count: int = Field(default=3, ge=1, le=20)
    retry_delay_seconds: float = Field(default=1.0, ge=0, le=60)
    resolve_before_register: bool = True


class OnboardingResult(BaseModel):
    """Protocol-neutral registration result cached locally for recovery."""

    model_config = ConfigDict(extra="allow", frozen=True)
    onboarding_id: str | None = None
    agent_id: str | None = None
    client_id: str | None = None
    protected_resource_id: str | None = None
    agent_token: str | None = None
