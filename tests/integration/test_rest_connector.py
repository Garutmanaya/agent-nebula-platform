import httpx
import pytest

from agent_nebula_platform.integrations.nebula import RestNebulaConnector


@pytest.mark.asyncio
async def test_rest_connector_uses_configured_paths():
    def handler(request):
        if request.url.path.endswith("/resolve"):
            return httpx.Response(404)
        return httpx.Response(201, json={"agent_id": "a"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    connector = RestNebulaConnector(base_url="https://nebula.example", client=client)
    assert await connector.resolve_onboarding({}) is None
    assert (await connector.onboard({}))["agent_id"] == "a"
    await client.aclose()
