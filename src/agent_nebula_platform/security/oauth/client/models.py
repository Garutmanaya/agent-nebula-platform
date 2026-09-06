"""Typed OAuth client runtime models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OAuthTokenRequest(BaseModel):
    """Describe one audience- and scope-specific token request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    resource: str = Field(min_length=1, max_length=4096)
    scopes: tuple[str, ...] = ()


class OAuthToken(BaseModel):
    """Represent a token response without exposing transport implementation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    access_token: str = Field(min_length=1)
    token_type: str = Field(min_length=1)
    expires_at: datetime
    scopes: tuple[str, ...] = ()


class ProtectedRequest(BaseModel):
    """Carry DPoP authorization headers for one outgoing request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    headers: dict[str, str]
    token: OAuthToken
