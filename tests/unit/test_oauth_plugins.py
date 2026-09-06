"""OAuth plugin registration tests."""

import pytest

from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.events import NullEventSink
from agent_nebula_platform.platform.state import MemoryStateStore
from agent_nebula_platform.security.oauth.client.plugin import OAuthClientPlugin
from agent_nebula_platform.security.oauth.protected_resource.plugin import (
    ProtectedResourcePlugin,
)


class Nebula:
    async def close(self):
        return None


@pytest.mark.asyncio
async def test_oauth_plugins_expose_services_without_owning_them() -> None:
    """Plugins register caller-composed services and remove them on close."""

    context = RuntimeContext(
        nebula=Nebula(),
        state_store=MemoryStateStore(),
        events=NullEventSink(),
    )
    oauth_service = object()
    resource_service = object()
    oauth = OAuthClientPlugin(oauth_service)
    resource = ProtectedResourcePlugin(resource_service)

    await oauth.initialize(context)
    await resource.initialize(context)
    assert set(context.services.names()) == {"oauth.client", "oauth.protected_resource"}

    await resource.close(context)
    await oauth.close(context)
    assert context.services.names() == ()
