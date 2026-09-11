from pathlib import Path

from agent_nebula_platform.integrations.nebula import (
    NebulaConfiguration,
    NebulaRegistrationAuthentication,
)
from agent_nebula_platform.integrations.nebula.onboarding import (
    build_agent_onboarding_payload,
)


def test_nebula_conf_open_full_verify(tmp_path: Path) -> None:
    (tmp_path / "ca.pem").write_text("placeholder", encoding="utf-8")
    path = tmp_path / "nebula.conf"
    path.write_text(
        """[nebula]\nbase_url=https://nebula.example\n[tls]\nmode=full-verify\nca_file=ca.pem\n[registration]\nauthentication=OPEN\n""",
        encoding="utf-8",
    )
    settings = NebulaConfiguration.load(path)
    assert settings.registration.authentication is NebulaRegistrationAuthentication.OPEN
    assert settings.tls.ca_file == (tmp_path / "ca.pem").resolve()


def test_agent_only_onboarding_has_a2a_provider_role_without_oauth_resource() -> None:
    payload = build_agent_onboarding_payload(
        entity_name="Echo",
        agent_card_uri="https://echo.example/.well-known/agent-card.json",
        protocols=("A2A",),
        capabilities=("echo",),
    )
    assert payload["roles"] == ["A2A_PROVIDER"]
    assert payload["authentication"] == {"method": "OPEN"}
    assert "protected_resource" not in payload


def test_agent_onboarding_uses_explicit_external_agent_id() -> None:
    """Keep Registry identity independent from the official A2A Agent Card name."""

    payload = build_agent_onboarding_payload(
        entity_name="Flight Booking Agent",
        agent_card_uri="https://example.test/.well-known/agent-card.json",
        protocols=("A2A",),
        capabilities=("booking",),
        external_agent_id="exp_test",
    )

    assert payload["entity_name"] == "Flight Booking Agent"
    assert payload["agent"]["metadata"]["external_agent_id"] == "exp_test"
