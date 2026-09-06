"""Tests for Runtime-owned OAuth identity recovery after onboarding."""

from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.platform.state import MemoryStateStore
from agent_nebula_platform.security.oauth.client import OnboardingOAuthClientIdentity


def _key(path: Path) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )


def test_identity_recovers_nested_oauth_client_id(tmp_path: Path) -> None:
    auth = tmp_path / "auth.pem"
    dpop = tmp_path / "dpop.pem"
    _key(auth)
    _key(dpop)
    state = MemoryStateStore()
    state.write(
        "caller",
        {"commit": {"profiles": {"OAUTH_CLIENT": {"client_id": "client-123"}}}},
    )
    identity = OnboardingOAuthClientIdentity(
        state_store=state,
        onboarding_state_key="caller",
        authentication_key_file=auth,
        dpop_key_file=dpop,
        key_id="kid",
    )
    assert identity.client_id() == "client-123"
    assert identity.public_jwks_document()["keys"][0]["kid"] == "kid"


def test_identity_fails_closed_before_onboarding(tmp_path: Path) -> None:
    auth = tmp_path / "auth.pem"
    dpop = tmp_path / "dpop.pem"
    _key(auth)
    _key(dpop)
    identity = OnboardingOAuthClientIdentity(
        state_store=MemoryStateStore(),
        onboarding_state_key="caller",
        authentication_key_file=auth,
        dpop_key_file=dpop,
        key_id="kid",
    )
    with pytest.raises(ConfigurationError, match="not provisioned"):
        identity.client_id()
