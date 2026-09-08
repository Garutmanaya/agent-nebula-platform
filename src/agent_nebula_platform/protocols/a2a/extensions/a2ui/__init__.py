"""A2UI binding for official A2A 1.x."""

from .client import A2UIClientExtension, A2UI_RENDERER_CAPABILITIES_METADATA_KEY
from .extension import A2UI_EXTENSION_BASE_URI, A2UI_EXTENSION_URI, ensure_a2ui_extension
from .parts import create_a2ui_action_part, create_a2ui_part, parse_a2ui_action_part
from .response import A2UIResponseParser

__all__ = [
    "A2UIClientExtension",
    "A2UI_EXTENSION_BASE_URI",
    "A2UI_EXTENSION_URI",
    "A2UI_RENDERER_CAPABILITIES_METADATA_KEY",
    "A2UIResponseParser",
    "create_a2ui_action_part",
    "create_a2ui_part",
    "parse_a2ui_action_part",
    "ensure_a2ui_extension",
]
