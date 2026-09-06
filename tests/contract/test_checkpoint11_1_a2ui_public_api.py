"""Checkpoint 11.1 public A2UI contract tests."""

from agent_nebula_platform.a2ui import (
    A2UI_SUPPORTED_VERSIONS,
    A2UICapabilities,
    A2UINegotiatedCapabilities,
    A2UIProtocolPolicy,
    A2UIRendererCapabilities,
)


def test_checkpoint11_1_a2ui_exports_are_stable() -> None:
    """Renderer consumers can import negotiation and capability contracts."""

    assert A2UI_SUPPORTED_VERSIONS == ("v0.9.1",)
    assert A2UICapabilities
    assert A2UINegotiatedCapabilities
    assert A2UIProtocolPolicy
    assert A2UIRendererCapabilities
