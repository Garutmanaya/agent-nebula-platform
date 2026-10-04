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


def test_server_security_factory_keeps_unsecured_cards_transparent():
    """Unified composition must not make authentication mandatory."""

    from agent_nebula_platform.protocols.a2a.security import A2AServerSecurityFactory

    card = _card([])
    composition = A2AServerSecurityFactory().create(
        agent_card=card,
        trust_bundle_file=None,
    )

    assert composition.service.required is False
    assert composition.protected_resource is None


def test_server_security_factory_accepts_pluggable_standard_authenticators():
    """Non-OAuth A2A schemes enter through the same server factory."""

    from agent_nebula_platform.protocols.a2a.security import A2AServerSecurityFactory

    card = _card([SecurityRequirement(schemes={"first": StringList()})])
    composition = A2AServerSecurityFactory().create(
        agent_card=card,
        trust_bundle_file=None,
        authenticators=(_Authenticator("api_key_security_scheme", {"first"}),),
    )

    assert composition.service.required is True
    assert composition.service.authenticate(_request())[0].scheme_name == "first"


def test_configured_security_loader_builds_api_key_authenticator(tmp_path):
    from agent_nebula_platform.protocols.a2a.security import A2AConfiguredSecurityLoader
    secret = tmp_path / "api-key"
    secret.write_text("secret")
    config = tmp_path / "a2aserver.conf"
    config.write_text(f'''[agent_card]\nname="unused"\n[security.api_key.first]\nsecret_file="{secret}"\nsubject="configured-client"\n''')
    authenticators = A2AConfiguredSecurityLoader().load(config)
    assert len(authenticators) == 1
    assert authenticators[0].scheme_type == "api_key_security_scheme"


def test_listener_requires_trust_bundle_for_client_certificate_authentication(tmp_path):
    from agent_nebula_platform.protocols.a2a.server.configuration.listener import A2AListenerConfigurationLoader
    config = tmp_path / "a2aserver.conf"
    config.write_text('''[server]\nhost="127.0.0.1"\nport=9999\n[server.tls]\nenabled=true\ncertificate_file="server.crt"\nprivate_key_file="server.key"\nrequire_client_certificate=true\n''')
    with pytest.raises(ConfigurationError, match="mTLS requires"):
        A2AListenerConfigurationLoader().load(config)
