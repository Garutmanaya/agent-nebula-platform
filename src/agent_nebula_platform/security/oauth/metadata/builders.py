"""Typed RFC 9728 metadata builders backed by Agent Nebula SDK validation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from agent_nebula_sdk.oauth.rfc9728 import ProtectedResourceMetadata

from agent_nebula_platform.platform.errors import ConfigurationError

from .metadata import ProtectedResourceMetadataDocument


class ProtectedResourceMetadataBuilder:
    """Build validated RFC 9728 metadata while preserving extension members."""

    def __init__(self, base_document: Mapping[str, Any] | None = None) -> None:
        self._document: dict[str, Any] = deepcopy(dict(base_document or {}))

    @classmethod
    def from_document(
        cls,
        document: Mapping[str, Any],
    ) -> ProtectedResourceMetadataBuilder:
        """Create a builder around an existing complete metadata document."""

        if not isinstance(document, Mapping):
            raise ConfigurationError(
                "Protected Resource Metadata must be a JSON object"
            )
        return cls(document)

    def resource(self, identifier: str) -> ProtectedResourceMetadataBuilder:
        """Set the exact protected-resource identifier."""

        self._document["resource"] = identifier
        return self

    def authorization_servers(
        self,
        issuers: Iterable[str],
    ) -> ProtectedResourceMetadataBuilder:
        """Replace advertised authorization-server issuer identifiers."""

        self._document["authorization_servers"] = self._unique_tokens(
            issuers,
            field_name="authorization_servers",
        )
        return self

    def scopes_supported(
        self,
        scopes: Iterable[str],
    ) -> ProtectedResourceMetadataBuilder:
        """Replace exact provider-specific OAuth scope identifiers."""

        self._document["scopes_supported"] = self._unique_tokens(
            scopes,
            field_name="scopes_supported",
        )
        return self

    def dpop(
        self,
        *,
        required: bool,
        algorithms: Iterable[str] = (),
    ) -> ProtectedResourceMetadataBuilder:
        """Configure DPoP requirements without implementing protocol logic locally."""

        self._document["dpop_bound_access_tokens_required"] = required
        self._document["dpop_signing_alg_values_supported"] = self._unique_tokens(
            algorithms,
            field_name="dpop_signing_alg_values_supported",
        )
        return self

    def bearer_methods(
        self,
        methods: Iterable[str],
    ) -> ProtectedResourceMetadataBuilder:
        """Replace supported bearer-token transport methods."""

        self._document["bearer_methods_supported"] = self._unique_tokens(
            methods,
            field_name="bearer_methods_supported",
        )
        return self

    def details(
        self,
        *,
        resource_name: str | None = None,
        documentation_uri: str | None = None,
        policy_uri: str | None = None,
        terms_uri: str | None = None,
    ) -> ProtectedResourceMetadataBuilder:
        """Set optional human-readable resource information."""

        if resource_name is not None:
            self._document["resource_name"] = resource_name
        if documentation_uri is not None:
            self._document["resource_documentation"] = documentation_uri
        if policy_uri is not None:
            self._document["resource_policy_uri"] = policy_uri
        if terms_uri is not None:
            self._document["resource_tos_uri"] = terms_uri
        return self

    def extension(self, name: str, value: Any) -> ProtectedResourceMetadataBuilder:
        """Set one RFC extension member without reducing its structure."""

        if not name.strip():
            raise ConfigurationError(
                "Protected-resource extension name must not be blank"
            )
        self._document[name] = deepcopy(value)
        return self

    def build(self) -> ProtectedResourceMetadataDocument:
        """Validate with the SDK and return the complete immutable document."""

        try:
            validated = ProtectedResourceMetadata.model_validate(self._document)
        except ValueError as exc:
            raise ConfigurationError(
                "Protected Resource Metadata is invalid",
                details={"reason": str(exc)},
            ) from exc

        # ``model_dump`` would preserve known and extra members, but the original
        # mapping is retained so caller-owned JSON representation remains the
        # authoritative source document after successful SDK validation.
        del validated
        return ProtectedResourceMetadataDocument.from_mapping(self._document)

    @staticmethod
    def _unique_tokens(values: Iterable[str], *, field_name: str) -> list[str]:
        """Validate exact opaque identifiers while preserving order."""

        tokens = [str(value) for value in values]
        if any(not value for value in tokens):
            raise ConfigurationError(f"{field_name} must not contain blank values")
        if len(set(tokens)) != len(tokens):
            raise ConfigurationError(f"{field_name} must not contain duplicate values")
        return tokens
