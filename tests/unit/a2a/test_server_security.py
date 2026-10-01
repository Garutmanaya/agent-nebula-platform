"""Tests for A2A 1.0 server security requirement semantics."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    APIKeySecurityScheme,
    SecurityRequirement,
    SecurityScheme,
    StringList,
)

from agent_nebula_platform.platform.errors import (
    AuthenticationError,
    ConfigurationError,
)
from agent_nebula_platform.protocols.a2a.security.security import (
    A2AAuthenticatedPrincipal,
    A2ASecurityRequest,
    A2AServerSecurityService,
)


@dataclass
class _Authenticator:
    scheme_type: str
    accepted_names: set[str]

    def authenticate(self, *, scheme_name, scheme, required_values, request):
        del scheme, required_values, request
        if scheme_name not in self.accepted_names:
            raise AuthenticationError("rejected")
        return A2AAuthenticatedPrincipal(scheme_name, "caller", {})


def _card(requirements):
    return AgentCard(
        name="secure-agent",
        description="test",
        version="1.0.0",
        supported_interfaces=[
            AgentInterface(
                url="https://agent.example/a2a",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        capabilities=AgentCapabilities(),
        default_input_modes=["text/plain"],
        default_output_modes=["application/json"],
        skills=[AgentSkill(id="test", name="Test", description="test", tags=["test"])],
        security_schemes={
            "first": SecurityScheme(
                api_key_security_scheme=APIKeySecurityScheme(
                    location="header", name="X-First"
                )
            ),
            "second": SecurityScheme(
                api_key_security_scheme=APIKeySecurityScheme(
                    location="header", name="X-Second"
                )
            ),
        },
        security_requirements=requirements,
    )


def _request():
    return A2ASecurityRequest(
        headers={}, http_method="POST", target_uri="https://agent.example/a2a"
    )


def test_security_requirements_are_or_between_entries():
    service = A2AServerSecurityService(
        agent_card=_card(
            [
                SecurityRequirement(schemes={"first": StringList()}),
                SecurityRequirement(schemes={"second": StringList()}),
            ]
        ),
        authenticators=(_Authenticator("api_key_security_scheme", {"second"}),),
    )
    assert service.authenticate(_request())[0].scheme_name == "second"


def test_security_requirement_is_and_within_entry():
    service = A2AServerSecurityService(
        agent_card=_card(
            [
                SecurityRequirement(
                    schemes={"first": StringList(), "second": StringList()}
                )
            ]
        ),
        authenticators=(_Authenticator("api_key_security_scheme", {"first"}),),
    )
    with pytest.raises(AuthenticationError):
        service.authenticate(_request())


def test_startup_fails_when_scheme_family_has_no_authenticator():
    service = A2AServerSecurityService(
        agent_card=_card([SecurityRequirement(schemes={"first": StringList()})]),
        authenticators=(),
    )
    with pytest.raises(ConfigurationError, match="no configured server authenticator"):
        service.validate_configuration()


def test_security_context_builder_preserves_sdk_context_and_nebula_principals():
    """Nebula authentication augments the official ServerCallContext."""

    from starlette.requests import Request

    from agent_nebula_platform.protocols.a2a.security.context import (
        A2ASecurityServerCallContextBuilder,
    )

    service = A2AServerSecurityService(
        agent_card=_card([SecurityRequirement(schemes={"first": StringList()})]),
        authenticators=(_Authenticator("api_key_security_scheme", {"first"}),),
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "server": ("agent.example", 443),
            "path": "/a2a",
            "query_string": b"",
            "headers": [(b"x-first", b"secret")],
        }
    )

    context = A2ASecurityServerCallContextBuilder(service).build(request)

    assert context.state["headers"]["x-first"] == "secret"
    principals = context.state["agent_nebula.security.principals"]
    assert principals[0].scheme_name == "first"
    assert principals[0].subject == "caller"


def test_security_context_builder_maps_authentication_failure_to_http_401():
    """Authentication failures stay at the HTTP boundary, not in A2A models."""

    from starlette.exceptions import HTTPException
    from starlette.requests import Request

    from agent_nebula_platform.protocols.a2a.security.context import (
        A2ASecurityServerCallContextBuilder,
    )

    service = A2AServerSecurityService(
        agent_card=_card([SecurityRequirement(schemes={"first": StringList()})]),
        authenticators=(_Authenticator("api_key_security_scheme", set()),),
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "server": ("agent.example", 443),
            "path": "/a2a",
            "query_string": b"",
            "headers": [],
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        A2ASecurityServerCallContextBuilder(service).build(request)

    assert exc_info.value.status_code == 401
