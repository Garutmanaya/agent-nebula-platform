"""Capability catalog for implemented and planned Agent Runtime modules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from agent_nebula_platform.platform.errors import ConfigurationError


class RuntimeCapability(StrEnum):
    """Stable identifiers for optional runtime capabilities."""

    CONFIGURATION = "configuration"
    LOGGING = "logging"
    TLS = "tls"
    ONBOARDING = "onboarding"
    DISCOVERY = "discovery"
    LIFECYCLE = "lifecycle"
    OAUTH_CLIENT = "oauth_client"
    PROTECTED_RESOURCE = "protected_resource"
    AGENT_CARD = "agent_card"
    HEALTH = "health"
    METRICS = "metrics"
    A2A_SERVER = "a2a_server"
    REST_SERVER = "rest_server"
    SKILLS = "skills"
    A2UI = "a2ui"
    A2UI_SESSION = "a2ui_session"
    TELEMETRY = "telemetry"
    SCHEDULER = "scheduler"
    PRESETS = "presets"


class CapabilityStatus(StrEnum):
    """Lifecycle status for one capability in the current release."""

    AVAILABLE = "available"
    PLANNED = "planned"


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    """Document one runtime capability without exposing unfinished APIs."""

    capability: RuntimeCapability
    status: CapabilityStatus
    checkpoint: str
    responsibility: str


_CAPABILITIES: tuple[CapabilityDescriptor, ...] = (
    CapabilityDescriptor(
        RuntimeCapability.CONFIGURATION,
        CapabilityStatus.AVAILABLE,
        "8",
        "Layered configuration, AGENT_RUNTIME_HOME, environment and CLI overrides, normalized paths, and strict plugin settings.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.LOGGING,
        CapabilityStatus.AVAILABLE,
        "1",
        "Caller-owned semantic event sinks and optional logging bridges.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.TLS,
        CapabilityStatus.AVAILABLE,
        "1",
        "Verified TLS context providers with explicit trust material.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.ONBOARDING,
        CapabilityStatus.AVAILABLE,
        "1",
        "Recoverable Agent Nebula onboarding orchestration.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.DISCOVERY,
        CapabilityStatus.AVAILABLE,
        "1",
        "Transport-neutral Agent Nebula discovery access.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.LIFECYCLE,
        CapabilityStatus.AVAILABLE,
        "1",
        "Explicit workload deregistration integration.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.OAUTH_CLIENT,
        CapabilityStatus.AVAILABLE,
        "2",
        "RFC-compliant token acquisition and DPoP-protected request construction.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.PROTECTED_RESOURCE,
        CapabilityStatus.AVAILABLE,
        "7",
        "RFC 9068/RFC 9449 request authentication plus SDK-validated RFC 9728 metadata construction and publication.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.AGENT_CARD,
        CapabilityStatus.AVAILABLE,
        "7",
        "Typed Agent Card construction, authoritative document preservation, publication, and cross-document validation.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.HEALTH,
        CapabilityStatus.AVAILABLE,
        "3",
        "Health and readiness endpoint integration.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.METRICS,
        CapabilityStatus.AVAILABLE,
        "9",
        "Thread-safe counters, gauges, timings, JSON snapshots, and exporter ports.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.A2A_SERVER,
        CapabilityStatus.AVAILABLE,
        "6",
        "Secure immediate invocation plus asynchronous task lifecycle, cancellation, SSE event streaming, and push-notification ports.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.REST_SERVER,
        CapabilityStatus.AVAILABLE,
        "3",
        "Optional REST/FastAPI server integration.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.SKILLS,
        CapabilityStatus.AVAILABLE,
        "3",
        "Typed skill registry and method-specific authorization.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.A2UI,
        CapabilityStatus.AVAILABLE,
        "4",
        "Declarative A2UI surface validation, A2A DataPart serialization, and trusted action dispatch.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.A2UI_SESSION,
        CapabilityStatus.AVAILABLE,
        "11.5",
        "Persistent multi-agent A2UI sessions, surface navigation, synchronized data models, action history, task references, and resume.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.TELEMETRY,
        CapabilityStatus.AVAILABLE,
        "9",
        "Structured operational events with caller-approved console and JSON-lines sinks.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.SCHEDULER,
        CapabilityStatus.AVAILABLE,
        "9",
        "Startup, shutdown, one-shot, and interval background jobs with graceful cancellation.",
    ),
    CapabilityDescriptor(
        RuntimeCapability.PRESETS,
        CapabilityStatus.AVAILABLE,
        "5",
        "Embedded and standalone composition presets with explicit infrastructure ownership.",
    ),
)


def capability_catalog() -> tuple[CapabilityDescriptor, ...]:
    """Return the immutable runtime capability roadmap."""

    return _CAPABILITIES


def require_available(capability: RuntimeCapability) -> CapabilityDescriptor:
    """Return an implemented capability or fail explicitly for placeholders."""

    descriptor = next(item for item in _CAPABILITIES if item.capability is capability)
    if descriptor.status is not CapabilityStatus.AVAILABLE:
        raise ConfigurationError(
            f"Runtime capability '{capability.value}' is planned for checkpoint "
            f"{descriptor.checkpoint} but is not implemented"
        )
    return descriptor
