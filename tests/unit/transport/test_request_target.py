"""Tests for externally visible request-target resolution."""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from agent_nebula_platform.platform.transport.http import RequestTargetResolver


def _client(resolver: RequestTargetResolver, base_url: str) -> TestClient:
    app = FastAPI()

    @app.get("/{path:path}")
    async def resolved_target(request: Request) -> dict[str, str]:
        return {"target": resolver.resolve(request)}

    return TestClient(app, base_url=base_url)


def test_direct_request_ignores_forwarded_headers() -> None:
    client = _client(RequestTargetResolver(), "https://internal.example:8462")
    response = client.get(
        "/a2a?value=1",
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "agents.example",
            "X-Forwarded-Prefix": "/agents/showcase/fleet/instance",
        },
    )
    assert response.json()["target"] == ("https://internal.example:8462/a2a?value=1")


def test_proxy_request_restores_prefix_and_omits_default_port() -> None:
    client = _client(
        RequestTargetResolver(trust_forwarded_headers=True),
        "http://127.0.0.1:8462",
    )
    response = client.get(
        "/a2a?value=1",
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "agents.example",
            "X-Forwarded-Port": "443",
            "X-Forwarded-Prefix": "/agents/showcase/fleet/instance",
        },
    )
    assert response.json()["target"] == (
        "https://agents.example/agents/showcase/fleet/instance/a2a?value=1"
    )


def test_proxy_request_preserves_non_default_port() -> None:
    client = _client(
        RequestTargetResolver(trust_forwarded_headers=True),
        "http://127.0.0.1:8462",
    )
    response = client.get(
        "/a2a",
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "aimlnode",
            "X-Forwarded-Port": "8080",
            "X-Forwarded-Prefix": "/agents/showcase/fleet/instance",
        },
    )
    assert response.json()["target"] == (
        "https://aimlnode:8080/agents/showcase/fleet/instance/a2a"
    )


def test_incomplete_proxy_headers_fall_back_to_direct_url() -> None:
    client = _client(
        RequestTargetResolver(trust_forwarded_headers=True),
        "http://127.0.0.1:8462",
    )
    response = client.get("/a2a", headers={"X-Forwarded-Proto": "https"})
    assert response.json()["target"] == "http://127.0.0.1:8462/a2a"
