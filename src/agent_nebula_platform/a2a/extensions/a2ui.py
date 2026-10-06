"""A2UI v1.0 capability advertisement on native A2A Agent Cards.

A2UI configuration remains owned by ``agent_nebula_platform.a2ui``. This
module owns only the A2A AgentExtension representation used by the migrated
native a2a-sdk path.
"""

from __future__ import annotations

from collections.abc import Sequence

from a2a.types import AgentCard, AgentExtension

from agent_nebula_platform.a2ui.models import A2UI_STABLE_VERSION
from agent_nebula_platform.platform.errors import ConfigurationError

A2UI_EXTENSION_BASE_URI = "https://a2ui.org/a2a-extension/a2ui"
A2UI_EXTENSION_URI = f"{A2UI_EXTENSION_BASE_URI}/{A2UI_STABLE_VERSION}"


def ensure_a2ui_extension(
    agent_card: AgentCard,
    *,
    supported_catalog_ids: Sequence[str] = (),
    accepts_inline_catalogs: bool = False,
) -> None:
    """Advertise configured A2UI capabilities through A2A extensions."""

    catalogs = _normalize_catalog_ids(supported_catalog_ids)
    expected_params: dict[str, object] = {
        A2UI_STABLE_VERSION: {
            "supportedCatalogIds": list(catalogs),
            "acceptsInlineCatalogs": accepts_inline_catalogs,
        }
    }

    for extension in agent_card.capabilities.extensions:
        if extension.uri != A2UI_EXTENSION_URI:
            continue
        if extension.required:
            raise ConfigurationError(
                "A2UI v1.0 extension must remain optional",
                details={"uri": A2UI_EXTENSION_URI},
            )
        if _params_as_mapping(extension.params) != expected_params:
            raise ConfigurationError(
                "A2UI Agent Card declaration conflicts with a2ui.conf",
                details={"uri": A2UI_EXTENSION_URI},
            )
        return

    agent_card.capabilities.extensions.append(
        AgentExtension(
            uri=A2UI_EXTENSION_URI,
            description="Provides agent-driven UI using A2UI v1.0.",
            required=False,
            params=expected_params,
        )
    )


def _normalize_catalog_ids(catalog_ids: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for catalog_id in catalog_ids:
        value = str(catalog_id).strip()
        if not value:
            raise ConfigurationError("A2UI supported catalog IDs must not be empty")
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _params_as_mapping(params: object) -> dict[str, object]:
    if params is None:
        return {}
    if isinstance(params, dict):
        return dict(params)
    try:
        from google.protobuf.json_format import MessageToDict
        from google.protobuf.message import Message

        if isinstance(params, Message):
            return dict(MessageToDict(params))
    except (ImportError, TypeError, ValueError):
        pass
    try:
        return dict(params)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("A2UI extension params are not a mapping") from exc
