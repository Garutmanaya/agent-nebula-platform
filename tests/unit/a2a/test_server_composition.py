"""Tests for standalone A2A server composition."""

from agent_nebula_platform.protocols.a2a.server.composition import (
    A2AStandaloneApplicationComposer,
)


def test_protected_resource_metadata_uri_uses_root_for_root_interface() -> None:
    """Preserve the standard RFC 9728 well-known URI for root A2A interfaces."""

    assert (
        A2AStandaloneApplicationComposer._protected_resource_metadata_uri(
            "https://localhost:9006/"
        )
        == "https://localhost:9006/.well-known/oauth-protected-resource"
    )


def test_protected_resource_metadata_uri_preserves_reverse_proxy_prefix() -> None:
    """Publish RFC 9728 metadata through the provider's public ingress prefix."""

    assert (
        A2AStandaloneApplicationComposer._protected_resource_metadata_uri(
            "https://aimlnode:9443/inventory/"
        )
        == "https://aimlnode:9443/inventory/.well-known/oauth-protected-resource"
    )
