"""Agent Nebula A2A extension semantics."""
from .health import ensure_health_extension
from .schema_contract import ensure_schema_contract_extension
from .skill_selection import NEBULA_SKILL_SELECTION_EXTENSION_URI, build_skill_selection_metadata, ensure_skill_selection_extension, require_supported_skill, selected_skill_id, validate_executable_skills
__all__ = ["NEBULA_SKILL_SELECTION_EXTENSION_URI", "build_skill_selection_metadata", "ensure_health_extension", "ensure_schema_contract_extension", "ensure_skill_selection_extension", "require_supported_skill", "selected_skill_id", "validate_executable_skills"]
