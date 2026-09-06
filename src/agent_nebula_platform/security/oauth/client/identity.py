"""Reusable file-backed OAuth identity resolved from Runtime onboarding state.

The identity keeps private keys external to the repository and resolves the
protocol-facing ``client_id`` lazily.  This allows caller agents and Studio
applications to start, publish their Agent Card and JWKS, complete Agent Nebula
onboarding through the Runtime plugin, and then acquire OAuth tokens without
application-specific recovery code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_nebula_sdk.core.encoding import encode_base64url
from agent_nebula_sdk.jose.jwk.parser import JwkParser
from agent_nebula_sdk.jose.thumbprint.service import JwkThumbprintService
from agent_nebula_sdk.oauth.rfc7523 import PrivateKeyJwtSigningKey
from agent_nebula_sdk.oauth.rfc9449 import DpopSigningKey
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.platform.state import RuntimeStateStore


class OnboardingOAuthClientIdentity:
    """Provide durable OAuth keys and a client ID recovered from onboarding.

    The optional client-ID file remains useful for externally provisioned
    clients.  When it is absent or empty, the identity reads the configured
    Runtime onboarding state and extracts the RFC-facing ``client_id`` from
    either the flattened Runtime model or the authoritative nested commit.
    """

    def __init__(
        self,
        *,
        state_store: RuntimeStateStore,
        onboarding_state_key: str,
        registration_state_key: str | None = None,
        authentication_key_file: Path,
        dpop_key_file: Path,
        key_id: str,
        algorithm: str = "ES256",
        client_id_file: Path | None = None,
    ) -> None:
        """Load external keys and retain non-secret identity lookup settings."""

        self._state_store = state_store
        self._state_key = onboarding_state_key
        self._registration_state_key = (
            registration_state_key or f"{onboarding_state_key}-oauth-registration"
        )
        self._client_id_file = client_id_file
        self._algorithm = algorithm
        self._key_id = key_id
        self._authentication_private_key = _load_ec_private_key(authentication_key_file)
        self._dpop_private_key = _load_ec_private_key(dpop_key_file)
        self._authentication_public_jwk = _public_jwk(
            self._authentication_private_key,
            key_id=key_id,
            algorithm=algorithm,
        )
        self._dpop_public_jwk = _public_jwk(
            self._dpop_private_key,
            key_id=f"{key_id}-dpop",
            algorithm=algorithm,
        )
        self._dpop_thumbprint = JwkThumbprintService().compute(self._dpop_public_jwk)

    def client_id(self) -> str:
        """Return the explicit or Runtime-onboarded protocol client identifier."""

        explicit = self._read_explicit_client_id()
        if explicit is not None:
            return explicit
        registration_state = self._state_store.read(self._registration_state_key)
        client_id = _client_id_from_state(registration_state)
        if client_id is None:
            legacy_state = self._state_store.read(self._state_key)
            client_id = _client_id_from_state(legacy_state)
        if client_id is None:
            raise ConfigurationError(
                "OAuth client identity is not provisioned; Registry CLIENT enrollment and "
                "RFC 7591 registration must complete before protected Provider invocation"
            )
        return client_id

    def authentication_key(self) -> PrivateKeyJwtSigningKey:
        """Return the RFC 7523 private-key JWT signing adapter."""

        return PrivateKeyJwtSigningKey(
            key_id=self._key_id,
            algorithm=self._algorithm,
            private_key=self._authentication_private_key,
        )

    def dpop_key(self) -> DpopSigningKey:
        """Return the RFC 9449 DPoP signing adapter."""

        return DpopSigningKey(
            algorithm=self._algorithm,
            private_key=self._dpop_private_key,
            public_jwk=self._dpop_public_jwk,
        )

    def dpop_key_thumbprint(self) -> str:
        """Return the RFC 7638 thumbprint used for token-cache isolation."""

        return self._dpop_thumbprint

    def public_jwks_document(self) -> dict[str, Any]:
        """Return the public client-authentication JWKS used during onboarding."""

        return {
            "keys": [
                self._authentication_public_jwk.model_dump(
                    mode="json",
                    exclude_none=True,
                )
            ]
        }

    def _read_explicit_client_id(self) -> str | None:
        """Read an optional externally provisioned client ID without requiring it."""

        if self._client_id_file is None or not self._client_id_file.is_file():
            return None
        value = self._client_id_file.read_text(encoding="utf-8").strip()
        return value or None


def _client_id_from_state(state: dict[str, Any] | None) -> str | None:
    """Extract a protocol client ID from current and legacy onboarding envelopes."""

    if not state:
        return None
    direct = state.get("client_id")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    commit = state.get("commit")
    if not isinstance(commit, dict):
        return None
    profiles = commit.get("profiles")
    if not isinstance(profiles, dict):
        return None
    profile = profiles.get("OAUTH_CLIENT") or profiles.get("oauth_client")
    if not isinstance(profile, dict):
        return None
    value = profile.get("client_id")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _load_ec_private_key(path: Path) -> ec.EllipticCurvePrivateKey:
    """Load one P-256 private key from a caller-approved external path."""

    if not path.is_file():
        raise ConfigurationError(f"OAuth private key file does not exist: {path}")
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise ConfigurationError(f"OAuth private key must use EC: {path}")
    if not isinstance(key.curve, ec.SECP256R1):
        raise ConfigurationError(f"OAuth private key must use P-256: {path}")
    return key


def _public_jwk(
    private_key: ec.EllipticCurvePrivateKey,
    *,
    key_id: str,
    algorithm: str,
):
    """Convert one P-256 public point into a validated SDK JWK model."""

    numbers = private_key.public_key().public_numbers()
    return JwkParser().parse_public_jwk(
        {
            "kty": "EC",
            "kid": key_id,
            "use": "sig",
            "alg": algorithm,
            "crv": "P-256",
            "x": encode_base64url(numbers.x.to_bytes(32, byteorder="big")),
            "y": encode_base64url(numbers.y.to_bytes(32, byteorder="big")),
        }
    )
