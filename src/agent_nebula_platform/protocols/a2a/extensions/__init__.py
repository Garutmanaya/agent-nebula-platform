"""Agent Nebula extensions layered on the official A2A protocol."""

from .skill_selection import (
    NEBULA_SKILL_SELECTION_EXTENSION_URI,
    build_skill_selection_metadata,
    ensure_skill_selection_extension,
    require_supported_skill,
    selected_skill_id,
    validate_executable_skills,
)

__all__ = [
    "NEBULA_SKILL_SELECTION_EXTENSION_URI",
    "build_skill_selection_metadata",
    "ensure_skill_selection_extension",
    "require_supported_skill",
    "selected_skill_id",
    "validate_executable_skills",
]
