"""A2A 1.0 server security requirement resolution and enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from a2a.types import AgentCard, SecurityScheme

from agent_nebula_platform.platform.errors import (
    AuthenticationError,
    ConfigurationError,
)


@dataclass(frozen=True, slots=True)
class A2ASecurityRequest:
    """Transport-neutral security material for one incoming A2A call."""

    headers: dict[str, str]
    http_method: str
    target_uri: str
    peer_certificate: object | None = None


@dataclass(frozen=True, slots=True)
class A2AAuthenticatedPrincipal:
    """Trusted result returned by one configured security authenticator."""

    scheme_name: str
    subject: str
    attributes: dict[str, Any]


class A2ASecuritySchemeAuthenticator(Protocol):
    """Authenticate one concrete official A2A SecurityScheme family."""

    @property
    def scheme_type(self) -> str:
        """Return the official SecurityScheme oneof field handled by this authenticator."""

    def authenticate(
        self,
        *,
        scheme_name: str,
        scheme: SecurityScheme,
        required_values: tuple[str, ...],
        request: A2ASecurityRequest,
    ) -> A2AAuthenticatedPrincipal:
        """Authenticate or raise AuthenticationError."""


class A2AServerSecurityService:
    """Evaluate A2A securityRequirements using OR-of-AND semantics."""

    def __init__(
        self,
        *,
        agent_card: AgentCard,
        authenticators: tuple[A2ASecuritySchemeAuthenticator, ...],
    ) -> None:
        self._agent_card = agent_card
        self._authenticators = {item.scheme_type: item for item in authenticators}
        if len(self._authenticators) != len(authenticators):
            raise ConfigurationError(
                "A2A security authenticator scheme types must be unique"
            )

    @property
    def required(self) -> bool:
        """Return whether the Agent Card requires authentication."""

        return bool(self._agent_card.security_requirements)

    def validate_configuration(self) -> None:
        """Fail startup when an advertised requirement cannot be enforced."""

        for requirement in self._agent_card.security_requirements:
            for scheme_name in requirement.schemes:
                scheme = self._agent_card.security_schemes.get(scheme_name)
                if scheme is None:
                    raise ConfigurationError(
                        "A2A security requirement references an undefined scheme",
                        details={"scheme_name": scheme_name},
                    )
                scheme_type = scheme.WhichOneof("scheme")
                if not scheme_type or scheme_type not in self._authenticators:
                    raise ConfigurationError(
                        "A2A security scheme has no configured server authenticator",
                        details={
                            "scheme_name": scheme_name,
                            "scheme_type": scheme_type,
                        },
                    )
                authenticator = self._authenticators[scheme_type]
                validate = getattr(authenticator, "validate_scheme", None)
                if callable(validate):
                    validate(scheme_name=scheme_name, scheme=scheme)

    def authenticate(
        self, request: A2ASecurityRequest
    ) -> tuple[A2AAuthenticatedPrincipal, ...]:
        """Satisfy one requirement alternative; all schemes in it must succeed."""

        if not self._agent_card.security_requirements:
            return ()
        failures: list[str] = []
        for requirement in self._agent_card.security_requirements:
            principals: list[A2AAuthenticatedPrincipal] = []
            try:
                for scheme_name, values in requirement.schemes.items():
                    scheme = self._agent_card.security_schemes[scheme_name]
                    scheme_type = scheme.WhichOneof("scheme")
                    authenticator = self._authenticators.get(scheme_type or "")
                    if authenticator is None:
                        raise AuthenticationError(
                            f"No authenticator is configured for A2A scheme {scheme_name!r}"
                        )
                    principals.append(
                        authenticator.authenticate(
                            scheme_name=scheme_name,
                            scheme=scheme,
                            required_values=tuple(values.list),
                            request=request,
                        )
                    )
            except AuthenticationError as exc:
                failures.append(str(exc))
                continue
            return tuple(principals)
        raise AuthenticationError(
            "A2A request did not satisfy any advertised security requirement",
            details={"alternatives": len(failures)},
        )
