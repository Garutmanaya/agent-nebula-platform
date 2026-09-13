"""Opt-in protocol observability for the Agent Nebula A2A binding.

The package is deliberately independent from client, server, security, and A2UI
business logic.  Protocol adapters emit structured events through the small
``A2AProtocolTracer`` interface; the default implementation is a no-op unless
explicitly enabled for diagnostics.
"""

from .events import A2AProtocolTraceEvent
from .tracer import A2AProtocolTracer, LoggingA2AProtocolTracer, NoOpA2AProtocolTracer

__all__ = [
    "A2AProtocolTraceEvent",
    "A2AProtocolTracer",
    "LoggingA2AProtocolTracer",
    "NoOpA2AProtocolTracer",
]
