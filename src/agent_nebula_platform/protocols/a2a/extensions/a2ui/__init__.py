"""A2UI binding for official A2A 1.x."""

from .extension import A2UI_EXTENSION_BASE_URI, A2UI_EXTENSION_URI, ensure_a2ui_extension
from .parts import create_a2ui_part

__all__ = [
    "A2UI_EXTENSION_BASE_URI",
    "A2UI_EXTENSION_URI",
    "create_a2ui_part",
    "ensure_a2ui_extension",
]
