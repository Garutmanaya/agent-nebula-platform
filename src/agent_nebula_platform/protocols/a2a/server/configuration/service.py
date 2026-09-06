"""Application service composing A2A server configuration loading and creation."""

from __future__ import annotations

from pathlib import Path

from a2a.types import AgentCard

from .factory import A2AAgentCardFactory
from .loader import A2AServerConfigurationLoader


class A2AServerConfigurationService:
    """Load an external A2A server configuration into an official Agent Card."""

    def __init__(
        self,
        loader: A2AServerConfigurationLoader | None = None,
        factory: A2AAgentCardFactory | None = None,
    ) -> None:
        """Create the service with replaceable loading and construction components."""

        self._loader = loader or A2AServerConfigurationLoader()
        self._factory = factory or A2AAgentCardFactory()

    def load_agent_card(self, path: Path) -> AgentCard:
        """Load, construct, and validate one externally configured Agent Card."""

        configuration = self._loader.load(path)
        return self._factory.create(configuration)
