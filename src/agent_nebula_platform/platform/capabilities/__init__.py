"""Runtime capability catalog and roadmap contracts."""

from .catalog import (
    CapabilityDescriptor,
    CapabilityStatus,
    RuntimeCapability,
    capability_catalog,
    require_available,
)

__all__ = [
    "CapabilityDescriptor",
    "CapabilityStatus",
    "RuntimeCapability",
    "capability_catalog",
    "require_available",
]
