"""Tests for dynamic A2A client security negotiation."""

from __future__ import annotations

import asyncio

from a2a.types import AgentCard, SecurityRequirement, SecurityScheme, StringList
from httpx import Headers

from agent_nebula_platform.protocols.a2a.client.client_credentials import (
    A2AApiKeyCredentialProvider,
    A2AStaticCredential,
)
from agent_nebula_platform.protocols.a2a.client.client_security import (
    A2AClientCredential,
    A2AClientSecurityInterceptor,
    A2AClientSecurityResolver,
)


def _card() -> AgentCard:
    card = AgentCard(
        name="provider",
        description="test",
        version="1",
        default_input_modes=["text"],
        default_output_modes=["text"],
    )
    scheme = SecurityScheme()
    scheme.api_key_security_scheme.name = "X-Partner-Key"
    scheme.api_key_security_scheme.location = "header"
    card.security_schemes["partner"].CopyFrom(scheme)
    card.security_requirements.append(
        SecurityRequirement(schemes={"partner": StringList()})
    )
    return card


def test_resolver_uses_scheme_type_not_scheme_name() -> None:
    provider = A2AApiKeyCredentialProvider((A2AStaticCredential("partner", "secret"),))
    resolved = A2AClientSecurityResolver((provider,)).resolve(
        agent_card=_card(), method="send_message"
    )
    assert resolved.schemes[0].scheme_name == "partner"
    assert resolved.schemes[0].scheme.WhichOneof("scheme") == "api_key_security_scheme"


class _RequestBoundProvider:
    scheme_type = "api_key_security_scheme"

    def can_satisfy(self, request):
        return True

    async def acquire(self, request):
        return A2AClientCredential(headers=(("DPoP", "initial"),))

    async def acquire_for_request_target(self, request, *, http_method, target_uri):
        return A2AClientCredential(
            headers=(("X-Target", f"{http_method} {target_uri}"),)
        )


def test_request_bound_security_uses_actual_http_target_without_query() -> None:
    interceptor = A2AClientSecurityInterceptor(
        A2AClientSecurityResolver((_RequestBoundProvider(),))
    )
    headers = Headers()
    asyncio.run(
        interceptor.apply_http_request_security(
            agent_card=_card(),
            http_method="POST",
            target_uri="https://provider.example/a2a/message:send?trace=1#ignored",
            headers=headers,
        )
    )
    assert headers["X-Target"] == "POST https://provider.example/a2a/message:send"
