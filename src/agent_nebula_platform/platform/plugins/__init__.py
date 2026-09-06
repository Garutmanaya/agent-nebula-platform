"""Generic plugin contracts and registry for the secure-agent platform.

Concrete plugins are colocated with the functional module they extend.
"""

from .base import RuntimePlugin, RuntimePluginPhase
from .registry import PluginRegistry, PluginStatus

__all__ = [
    "PluginRegistry",
    "PluginStatus",
    "RuntimePlugin",
    "RuntimePluginPhase",
]
