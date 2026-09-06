"""Fail-closed semantic validation for configured A2A 1.0 Agent Cards.

Required-field validation is delegated to the official ``a2a-python`` utility.
Runtime adds only configuration-boundary invariants that are not represented by
protobuf field annotations, such as cross-references and uniqueness.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from urllib.parse import urlparse

from a2a.types import AgentCard, InvalidParamsError, SecurityRequirement
from a2a.utils.constants import TransportProtocol
from a2a.utils.proto_utils import validate_proto_required_fields

from agent_nebula_platform.platform.errors import ConfigurationError


class A2AAgentCardValidator:
    """Validate official A2A requirements plus Runtime publication invariants."""

    def validate(self, agent_card: AgentCard) -> None:
        """Reject incomplete or internally inconsistent Agent Card configuration."""

        self._validate_official_required_fields(agent_card)
        self._validate_interfaces(agent_card)
        self._validate_skill_identifiers(agent_card)
        self._validate_security_schemes(agent_card)
        self._validate_requirements(
            agent_card.security_requirements,
            agent_card,
            location="agent_card.security_requirements",
        )
        for index, skill in enumerate(agent_card.skills):
            self._validate_requirements(
                skill.security_requirements,
                agent_card,
                location=f"agent_card.skills[{index}].security_requirements",
            )

    @staticmethod
    def _validate_official_required_fields(agent_card: AgentCard) -> None:
        """Apply required-field rules defined by the official A2A protobuf."""

        try:
            validate_proto_required_fields(agent_card)
        except InvalidParamsError as exc:
            raise ConfigurationError(
                "A2A Agent Card is missing fields required by the A2A 1.0 model",
                details={"validation": exc.data},
            ) from exc

    def _validate_interfaces(self, agent_card: AgentCard) -> None:
        """Validate interface addressing according to its official binding."""

        for index, interface in enumerate(agent_card.supported_interfaces):
            field = f"agent_card.supported_interfaces[{index}].url"
            if interface.protocol_binding in {
                TransportProtocol.JSONRPC,
                TransportProtocol.HTTP_JSON,
            }:
                self._require_absolute_url(interface.url, field)
            elif interface.protocol_binding == TransportProtocol.GRPC:
                self._require_grpc_authority(interface.url, field)
            else:
                raise ConfigurationError(
                    "A2A Agent Card interface uses an unsupported protocol binding",
                    details={
                        "field": field,
                        "protocol_binding": interface.protocol_binding,
                    },
                )

    @staticmethod
    def _validate_skill_identifiers(agent_card: AgentCard) -> None:
        """Reject duplicate skill identifiers that would make handler binding ambiguous."""

        duplicates = sorted(
            identifier
            for identifier, count in Counter(
                skill.id for skill in agent_card.skills
            ).items()
            if identifier and count > 1
        )
        if duplicates:
            raise ConfigurationError(
                "A2A Agent Card skill identifiers must be unique",
                details={"duplicates": duplicates},
            )

    @staticmethod
    def _validate_security_schemes(agent_card: AgentCard) -> None:
        """Require every configured security scheme to select one official A2A type."""

        for name, scheme in agent_card.security_schemes.items():
            if not name.strip():
                raise ConfigurationError("A2A security scheme name must not be blank")
            if scheme.WhichOneof("scheme") is None:
                raise ConfigurationError(
                    "A2A security scheme must configure one supported scheme type",
                    details={"scheme": name},
                )

    @staticmethod
    def _validate_requirements(
        requirements: Iterable[SecurityRequirement],
        agent_card: AgentCard,
        *,
        location: str,
    ) -> None:
        """Validate requirement references while preserving A2A OR-of-AND semantics."""

        known_schemes = set(agent_card.security_schemes.keys())
        for index, requirement in enumerate(requirements):
            if not requirement.schemes:
                raise ConfigurationError(
                    "A2A security requirement must reference at least one scheme",
                    details={"location": location, "index": index},
                )
            unknown = sorted(set(requirement.schemes.keys()) - known_schemes)
            if unknown:
                raise ConfigurationError(
                    "A2A security requirement references undefined schemes",
                    details={
                        "location": location,
                        "index": index,
                        "schemes": unknown,
                    },
                )

    @staticmethod
    def _require_absolute_url(value: str, field: str) -> None:
        """Require an absolute HTTP(S) URL without imposing deployment host values."""

        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigurationError(
                "A2A Agent Card interface URL must be an absolute HTTP(S) URL",
                details={"field": field, "value": value},
            )

    @staticmethod
    def _require_grpc_authority(value: str, field: str) -> None:
        """Require a host and port for an official gRPC interface."""

        parsed = urlparse(value if "://" in value else f"grpc://{value}")
        if parsed.scheme != "grpc" or not parsed.hostname or parsed.port is None:
            raise ConfigurationError(
                "A2A gRPC interface must identify a host and port",
                details={"field": field, "value": value},
            )
        if parsed.path not in {"", "/"}:
            raise ConfigurationError(
                "A2A gRPC interface must not contain an HTTP path",
                details={"field": field, "value": value},
            )
