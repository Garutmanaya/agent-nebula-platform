"""Unified server-side composition for official A2A security schemes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from a2a.types import AgentCard

from agent_nebula_platform.security.oauth.protected_resource import ProtectedResourceService

from .oauth_security import A2AOAuth2ProtectedResourceAuthenticator
from .protected_resource import (
    A2AProtectedResourceComposition,
    A2AProtectedResourceFactory,
)
from .security import A2ASecuritySchemeAuthenticator, A2AServerSecurityService


@dataclass(frozen=True, slots=True)
class A2AServerSecurityComposition:
    """Security resources composed for one official A2A Agent Card."""

    service: A2AServerSecurityService
    protected_resource: A2AProtectedResourceComposition | None = None


class A2AServerSecurityFactory:
    """Compose all server-side A2A authentication through one boundary.

    AGENT NEBULA SECURITY: A2A defines the advertised security schemes and
    requirement semantics, while Agent Nebula supplies credential validation.
    This factory is the single Platform composition point that joins those two
    responsibilities. Scheme-specific validators remain pluggable adapters;
    OAuth protected-resource construction remains delegated to its existing
    RFC 8414/RFC 9728 implementation.
    """

    def __init__(
        self,
        *,
        protected_resource_factory: A2AProtectedResourceFactory | None = None,
    ) -> None:
        self._protected_resource_factory = (
            protected_resource_factory or A2AProtectedResourceFactory()
        )

    def create(
        self,
        *,
        agent_card: AgentCard,
        trust_bundle_file: Path | None,
        authenticators: tuple[A2ASecuritySchemeAuthenticator, ...] = (),
        protected_resource_service: ProtectedResourceService | None = None,
    ) -> A2AServerSecurityComposition:
        """Build the security service and any OAuth-owned lifecycle resources.

        ``authenticators`` is the extension seam for API-key, HTTP-auth, OIDC,
        and mTLS validators. Step 1 centralizes composition without changing
        existing application configuration; subsequent examples can supply
        those validators through configuration-driven Platform adapters.
        """

        protected_resource = None
        if protected_resource_service is None:
            protected_resource = self._protected_resource_factory.create(
                agent_card=agent_card,
                trust_bundle_file=trust_bundle_file,
            )
            if protected_resource is not None:
                protected_resource_service = protected_resource.runtime.service
        configured = list(authenticators)
        configured_types = {item.scheme_type for item in configured}
        if (
            protected_resource_service is not None
            and "oauth2_security_scheme" not in configured_types
        ):
            configured.append(
                A2AOAuth2ProtectedResourceAuthenticator(protected_resource_service)
            )

        service = A2AServerSecurityService(
            agent_card=agent_card,
            authenticators=tuple(configured),
        )
        # Fail at composition time rather than waiting for the listener plugin
        # to start. Unsecured cards are valid and require no authenticators.
        service.validate_configuration()
        return A2AServerSecurityComposition(
            service=service,
            protected_resource=protected_resource,
        )
