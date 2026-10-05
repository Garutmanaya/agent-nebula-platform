"""A2A Schema Contract community extension Draft 0.1 advertisement.

This is a profile of A2A Protocol 1.0. It uses only the standard
``AgentCard.capabilities.extensions`` extension point and does not modify any
A2A core type. P1 intentionally supports inline JSON Schema contracts only.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from a2a.types import AgentCard, AgentExtension
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message
from agent_nebula_platform.platform.errors import ConfigurationError

A2A_SCHEMA_CONTRACT_EXTENSION_URI = "https://w3id.org/a2a-schema-contract/draft/0.1"
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
JSON_SCHEMA_MEDIA_TYPE = "application/schema+json"
JSON_MEDIA_TYPE = "application/json"

class SchemaContractSkill(Protocol):
    @property
    def skill_id(self) -> str: ...
    @property
    def schema_contract_id(self) -> str | None: ...
    @property
    def input_schema(self) -> Mapping[str, Any] | None: ...
    @property
    def output_schema(self) -> Mapping[str, Any] | None: ...

def ensure_schema_contract_extension(agent_card: AgentCard, skills: Sequence[SchemaContractSkill]) -> None:
    """Advertise registered inline contracts through the official extension model."""
    contracts: list[dict[str, object]] = []
    for skill in skills:
        contract_id = getattr(skill, "schema_contract_id", None)
        input_schema = getattr(skill, "input_schema", None)
        output_schema = getattr(skill, "output_schema", None)
        if contract_id is None:
            if input_schema is not None or output_schema is not None:
                raise ConfigurationError(
                    "Schema-constrained skill requires schema_contract_id",
                    details={"skill_id": skill.skill_id},
                )
            continue
        contracts.append(_build_contract(skill))
    if not contracts:
        return
    expected_params: dict[str, object] = {"catalog": {"inline": {"contracts": contracts}}}
    for extension in agent_card.capabilities.extensions:
        if extension.uri != A2A_SCHEMA_CONTRACT_EXTENSION_URI:
            continue
        if extension.required:
            raise ConfigurationError("A2A Schema Contract extension must remain optional in P1", details={"uri": A2A_SCHEMA_CONTRACT_EXTENSION_URI})
        if _params_as_mapping(extension.params) != expected_params:
            raise ConfigurationError("A2A Schema Contract extension conflicts with registered skill contracts", details={"uri": A2A_SCHEMA_CONTRACT_EXTENSION_URI})
        return
    agent_card.capabilities.extensions.append(AgentExtension(
        uri=A2A_SCHEMA_CONTRACT_EXTENSION_URI,
        description="Advertises machine-readable application payload contracts using A2A Schema Contract community extension Draft 0.1.",
        required=False,
        params=expected_params,
    ))

def _build_contract(skill: SchemaContractSkill) -> dict[str, object]:
    contract_id = str(skill.schema_contract_id or "").strip()
    if not contract_id:
        raise ConfigurationError("Schema-constrained skill requires schema_contract_id", details={"skill_id": skill.skill_id})
    return {"id": contract_id, "skillIds": [skill.skill_id], "input": _build_direction(skill.input_schema), "output": _build_direction(skill.output_schema)}

def _build_direction(schema: Mapping[str, Any] | None) -> dict[str, object]:
    if schema is None:
        return {"presence": "none"}
    return {"presence": "required", "representations": [{"id": "json", "mediaType": JSON_MEDIA_TYPE, "schema": {"inline": dict(schema), "mediaType": JSON_SCHEMA_MEDIA_TYPE, "dialect": JSON_SCHEMA_DIALECT}}]}

def _params_as_mapping(params: object) -> dict[str, object]:
    if params is None: return {}
    if isinstance(params, dict): return dict(params)
    if isinstance(params, Message): return dict(MessageToDict(params))
    try: return dict(params)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc: raise ConfigurationError("A2A Schema Contract extension params are not a mapping") from exc
