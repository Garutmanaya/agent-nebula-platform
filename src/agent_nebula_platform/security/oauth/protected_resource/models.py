"""Typed protected-resource runtime models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProtectedResourceRequest(BaseModel):
    """Describe the security-relevant parts of one incoming request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    access_token: str = Field(min_length=1)
    dpop_proof: str | None = Field(default=None, min_length=1)
    http_method: str = Field(min_length=1, max_length=32)
    target_uri: str = Field(min_length=1, max_length=4096)
    required_scopes: tuple[str, ...] = ()
    nonce_context: str | None = None


class AuthorizedRequestContext(BaseModel):
    """Carry trusted caller identity and granted scopes into business code."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", frozen=True)

    subject: str
    client_id: str
    granted_scopes: tuple[str, ...]
    token_claims: object
    dpop_proof: object | None = None
