"""Agent Nebula deterministic skill-selection extension for official A2A."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any
from a2a.types import AgentCard, AgentExtension
from google.protobuf.json_format import ParseDict
from google.protobuf.struct_pb2 import Struct
from agent_nebula_platform.platform.errors import ConfigurationError
NEBULA_SKILL_SELECTION_EXTENSION_URI = 'https://agentnebula.ai/extensions/a2a/skill-selection/v1'
NEBULA_SKILL_SELECTION_METADATA_KEY = NEBULA_SKILL_SELECTION_EXTENSION_URI
NEBULA_SKILL_ID_FIELD = 'skillId'

def ensure_skill_selection_extension(agent_card: AgentCard, *, required: bool) -> None:
    """Publish the Nebula skill-selection extension on an official Agent Card.

    Args:
        agent_card: Official A2A Agent Card to update before it is published.
        required: Whether clients must activate the extension for requests.

    Raises:
        ConfigurationError: If the card already declares the URI with a
            conflicting ``required`` value.
    """
    for extension in agent_card.capabilities.extensions:
        if extension.uri != NEBULA_SKILL_SELECTION_EXTENSION_URI:
            continue
        if extension.required != required:
            raise ConfigurationError('Nebula A2A skill-selection extension has conflicting required setting', details={'uri': NEBULA_SKILL_SELECTION_EXTENSION_URI, 'configured_required': extension.required, 'required': required})
        return
    agent_card.capabilities.extensions.append(AgentExtension(uri=NEBULA_SKILL_SELECTION_EXTENSION_URI, description='Agent Nebula deterministic selection of an advertised AgentSkill.id using standard A2A extension metadata', required=required))

def require_supported_skill(agent_card: AgentCard, skill_id: str) -> None:
    """Validate a client-selected skill against the remote Agent Card.

    Args:
        agent_card: Remote official Agent Card discovered by the client.
        skill_id: Exact advertised ``AgentSkill.id`` selected by the caller.

    Raises:
        ConfigurationError: If the extension or selected skill is not advertised.
    """
    normalized = _normalize_skill_id(skill_id)
    if not any((extension.uri == NEBULA_SKILL_SELECTION_EXTENSION_URI for extension in agent_card.capabilities.extensions)):
        raise ConfigurationError('A2A agent does not advertise the Nebula skill-selection extension', details={'uri': NEBULA_SKILL_SELECTION_EXTENSION_URI})
    if not any((skill.id == normalized for skill in agent_card.skills)):
        raise ConfigurationError(f'A2A skill is not advertised by the remote agent: {normalized}', details={'skill_id': normalized})

def build_skill_selection_metadata(skill_id: str) -> Struct:
    """Build standards-compliant SendMessageRequest metadata for one skill.

    Args:
        skill_id: Exact ``AgentSkill.id`` selected by the A2A client.

    Returns:
        Protobuf Struct namespaced by the extension URI.
    """
    normalized = _normalize_skill_id(skill_id)
    return ParseDict({NEBULA_SKILL_SELECTION_METADATA_KEY: {NEBULA_SKILL_ID_FIELD: normalized}}, Struct())

def selected_skill_id(*, metadata: Mapping[str, Any], requested_extensions: set[str]) -> str | None:
    """Read and validate the selected skill from an incoming A2A request.

    Args:
        metadata: Request metadata exposed by official ``RequestContext``.
        requested_extensions: Extension URIs activated through the A2A binding.

    Returns:
        Selected skill ID, or ``None`` when this extension was not activated.

    Raises:
        ConfigurationError: If activated extension metadata is absent or invalid.
    """
    if NEBULA_SKILL_SELECTION_EXTENSION_URI not in requested_extensions:
        return None
    extension_metadata = metadata.get(NEBULA_SKILL_SELECTION_METADATA_KEY)
    if not isinstance(extension_metadata, Mapping):
        raise ConfigurationError('Nebula A2A skill-selection metadata is required when the extension is active')
    skill_id = extension_metadata.get(NEBULA_SKILL_ID_FIELD)
    if not isinstance(skill_id, str):
        raise ConfigurationError('Nebula A2A skill-selection metadata must contain string skillId')
    return _normalize_skill_id(skill_id)

def validate_executable_skills(agent_card: AgentCard, skill_ids: Sequence[str]) -> tuple[str, ...]:
    """Validate executable handlers against all skills published by the Agent Card."""
    normalized = tuple((_normalize_skill_id(skill_id) for skill_id in skill_ids))
    if not normalized:
        raise ConfigurationError('A2A server requires at least one executable skill')
    if len(set(normalized)) != len(normalized):
        raise ConfigurationError('A2A executable skill identifiers must be unique')
    published = {skill.id for skill in agent_card.skills}
    missing = sorted(set(normalized) - published)
    if missing:
        raise ConfigurationError('A2A executable skills are not published by a2aserver.conf', details={'skill_ids': missing})
    return normalized

def _normalize_skill_id(skill_id: str) -> str:
    normalized = skill_id.strip()
    if not normalized:
        raise ConfigurationError('A2A skill_id must not be blank')
    return normalized
