"""Checkpoint 4 public API and capability contracts."""

from agent_nebula_platform.a2ui import A2UIActionRequest, A2UIService, A2UISurface
from agent_nebula_platform.a2ui.plugin import A2UIPlugin
from agent_nebula_platform.platform.capabilities import (
    RuntimeCapability,
    require_available,
)


def test_checkpoint4_a2ui_exports_are_available() -> None:
    assert A2UISurface
    assert A2UIActionRequest
    assert A2UIService
    assert A2UIPlugin
    assert require_available(RuntimeCapability.A2UI).checkpoint == "4"
