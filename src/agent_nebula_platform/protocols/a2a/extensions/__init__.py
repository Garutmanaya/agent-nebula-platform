from .health import (
    NEBULA_HEALTH_EXTENSION_URI,
    ensure_health_extension,
)
"""Agent Nebula extensions layered on the official A2A protocol."""

from .schema_contract import A2A_SCHEMA_CONTRACT_EXTENSION_URI, ensure_schema_contract_extension

from .skill_selection import (
    NEBULA_SKILL_SELECTION_EXTENSION_URI,
    build_skill_selection_metadata,
    ensure_skill_selection_extension,
    require_supported_skill,
    selected_skill_id,
    validate_executable_skills,
)

__all__ = [
    "NEBULA_HEALTH_EXTENSION_URI",
    "NEBULA_SKILL_SELECTION_EXTENSION_URI",
    "A2A_SCHEMA_CONTRACT_EXTENSION_URI",
    "ensure_health_extension",
    "build_skill_selection_metadata",
    "ensure_skill_selection_extension",
    "ensure_schema_contract_extension",
    "require_supported_skill",
    "selected_skill_id",
    "validate_executable_skills",
]
