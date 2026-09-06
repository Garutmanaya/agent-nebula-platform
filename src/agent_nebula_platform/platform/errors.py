"""Stable exceptions exposed by Agent Runtime."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class AgentRuntimeError(Exception):
    """Base exception for runtime integration failures."""

    def __init__(
        self, message: str, *, details: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.details = dict(details or {})


class ConfigurationError(AgentRuntimeError, ValueError):
    """Raised when runtime composition or configuration is invalid."""


class PluginError(AgentRuntimeError):
    """Raised when a required plugin cannot initialize or close safely."""


class RemoteServiceError(AgentRuntimeError):
    """Raised when an Agent Nebula or OAuth operation fails remotely."""


class AuthenticationError(AgentRuntimeError):
    """Raised when remote credentials or a protected request are rejected."""


class AuthorizationError(AgentRuntimeError):
    """Raised when authenticated identity lacks provider-local authority."""
