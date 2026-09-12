"""SDK-backed onboarding payload builders exposed as Runtime capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_nebula_sdk.oauth.rfc7591 import ClientMetadata
from agent_nebula_sdk.oauth.rfc9728 import ProtectedResourceMetadata
from agent_nebula_sdk.onboarding import (
    AgentRegistrationInput,
    AgentRole,
    OAuthClientRegistrationInput,
    OnboardingAuthenticationInput,
    OnboardingAuthenticationMethod,
    OnboardingRequest,
    ProtectedResourceRegistrationInput,
)


def build_agent_onboarding_payload(
    *,
    entity_name: str,
    agent_card_uri: str,
    protocols: tuple[str, ...],
    capabilities: tuple[str, ...],
    authentication_method: str = "OPEN",
    external_agent_id: str | None = None,
) -> dict[str, Any]:
    """Build A2A provider onboarding without OAuth resource roles."""

    method = OnboardingAuthenticationMethod(authentication_method)
    request = OnboardingRequest(
        entity_name=entity_name,
        roles=frozenset((AgentRole.A2A_PROVIDER,)),
        authentication=OnboardingAuthenticationInput(
            method=method,
            credential=(
                "transport-api-key"
                if method is OnboardingAuthenticationMethod.API_KEY
                else None
            ),
        ),
        agent=AgentRegistrationInput(
            agent_card_uri=agent_card_uri,
            protocols=frozenset(protocols),
            capabilities=capabilities,
            metadata=(
                {"external_agent_id": external_agent_id}
                if external_agent_id is not None
                else {}
            ),
        ),
    )
    return _public_payload(request)


def build_provider_onboarding_payload(
    *,
    entity_name: str,
    agent_card_uri: str,
    protected_resource_metadata_uri: str,
    protected_resource_document: Mapping[str, Any],
    protocols: tuple[str, ...],
    capabilities: tuple[str, ...],
    authentication_method: str = "API_KEY",
    resource_type: str = "A2A_AGENT",
    external_agent_id: str | None = None,
) -> dict[str, Any]:
    """Build a validated provider onboarding wire payload without credentials."""

    method = OnboardingAuthenticationMethod(authentication_method)
    request = OnboardingRequest(
        entity_name=entity_name,
        roles=frozenset((AgentRole.A2A_PROVIDER, AgentRole.OAUTH_PROTECTED_RESOURCE)),
        authentication=OnboardingAuthenticationInput(
            method=method,
            credential=(
                "transport-api-key"
                if method is OnboardingAuthenticationMethod.API_KEY
                else None
            ),
        ),
        agent=AgentRegistrationInput(
            agent_card_uri=agent_card_uri,
            protocols=frozenset(protocols),
            capabilities=capabilities,
            metadata=(
                {"external_agent_id": external_agent_id}
                if external_agent_id is not None
                else {}
            ),
        ),
        protected_resource=ProtectedResourceRegistrationInput(
            metadata=ProtectedResourceMetadata.model_validate(
                dict(protected_resource_document)
            ),
            metadata_uri=protected_resource_metadata_uri,
            agent_card_uri=agent_card_uri,
            resource_type=resource_type,
        ),
    )
    return _public_payload(request)


def build_oauth_client_onboarding_payload(
    *,
    entity_name: str,
    agent_card_uri: str,
    jwks_uri: str,
    protocols: tuple[str, ...],
    capabilities: tuple[str, ...],
    client_name: str,
    authentication_method: str = "API_KEY",
) -> dict[str, Any]:
    """Build a validated OAuth-client onboarding wire payload."""

    method = OnboardingAuthenticationMethod(authentication_method)
    request = OnboardingRequest(
        entity_name=entity_name,
        roles=frozenset((AgentRole.OAUTH_CLIENT,)),
        authentication=OnboardingAuthenticationInput(
            method=method,
            credential=(
                "transport-api-key"
                if method is OnboardingAuthenticationMethod.API_KEY
                else None
            ),
        ),
        agent=AgentRegistrationInput(
            agent_card_uri=agent_card_uri,
            protocols=frozenset(protocols),
            capabilities=capabilities,
        ),
        oauth_client=OAuthClientRegistrationInput(
            metadata=ClientMetadata(
                client_name=client_name,
                grant_types=("client_credentials",),
                response_types=(),
                token_endpoint_auth_method="private_key_jwt",
                jwks_uri=jwks_uri,
            )
        ),
    )
    return _public_payload(request)


def _public_payload(request: OnboardingRequest) -> dict[str, Any]:
    """Remove transport-only placeholders and Runtime-internal context."""

    payload = request.model_dump(mode="json", exclude_none=True)
    payload["authentication"].pop("credential", None)
    payload.pop("context", None)
    return payload
