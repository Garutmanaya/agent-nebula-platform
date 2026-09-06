"""Public API contract for phased server startup support."""

from agent_nebula_platform.platform.plugins import RuntimePluginPhase
from agent_nebula_platform.platform.transport.fastapi import (
    UvicornRuntimeServer,
    UvicornServerSettings,
)


def test_runtime_phase_types_are_public() -> None:
    """Expose the lifecycle boundary required by third-party server integrations."""

    assert RuntimePluginPhase.PRE_SERVER.value == "pre_server"
    assert RuntimePluginPhase.POST_SERVER.value == "post_server"
    assert UvicornRuntimeServer
    assert UvicornServerSettings
