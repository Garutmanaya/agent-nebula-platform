"""Construction of official A2A 1.0 Agent Cards from external configuration.

This module intentionally performs no protocol re-modeling.  The TOML mapping
is passed directly into the official ``a2a-python`` protobuf ``AgentCard`` so
new optional fields supported by that model do not require a parallel Nebula
Agent Card hierarchy.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from a2a.types import AgentCard
from google.protobuf.message import DecodeError

from agent_nebula_platform.platform.errors import ConfigurationError

from .validation import A2AAgentCardValidator


class A2AAgentCardFactory:
    """Build and validate official ``a2a-python`` Agent Card instances."""

    def __init__(self, validator: A2AAgentCardValidator | None = None) -> None:
        """Create the factory with an injectable semantic validator."""

        self._validator = validator or A2AAgentCardValidator()

    def create(self, configuration: Mapping[str, Any]) -> AgentCard:
        """Construct one official Agent Card from a configuration mapping."""

        normalized = self._normalize_security_requirements(configuration)
        try:
            agent_card = AgentCard(**normalized)
        except (DecodeError, TypeError, ValueError) as exc:
            raise ConfigurationError(
                "A2A Agent Card configuration does not match the A2A 1.0 model"
            ) from exc
        self._validator.validate(agent_card)
        return agent_card

    @staticmethod
    def _normalize_security_requirements(
        configuration: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Translate TOML scope lists into protobuf ``StringList`` mappings.

        TOML naturally expresses an A2A requirement as
        ``schemes = { oauth = ["scope"] }``.  Protobuf constructors require
        each map value to use the wrapper shape ``{"list": [...]}``.  This is
        the only configuration-specific structural adaptation performed here.
        """

        document = deepcopy(dict(configuration))

        def normalize(requirements: object) -> None:
            """Normalize one list of requirement mappings in place."""

            if not isinstance(requirements, list):
                return
            for requirement in requirements:
                if not isinstance(requirement, dict):
                    continue
                schemes = requirement.get("schemes")
                if not isinstance(schemes, dict):
                    continue
                for name, scopes in tuple(schemes.items()):
                    if isinstance(scopes, list):
                        schemes[name] = {"list": scopes}

        normalize(document.get("security_requirements"))
        skills = document.get("skills")
        if isinstance(skills, list):
            for skill in skills:
                if isinstance(skill, dict):
                    normalize(skill.get("security_requirements"))
        return document
