"""Application service composing A2A server configuration loading and creation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from a2a.types import AgentCard

from agent_nebula_platform.platform.errors import ConfigurationError

from .factory import A2AAgentCardFactory
from .loader import A2AServerConfigurationLoader


@dataclass(frozen=True, slots=True)
class A2AServerConfiguration:
    """Resolved A2A server publication configuration.

    ``agent_card_url`` is Agent Nebula hosting configuration and is deliberately
    kept outside the official A2A ``AgentCard`` protobuf.  The Agent Card's
    ``supported_interfaces`` remain the authoritative interaction endpoints.
    """

    agent_card: AgentCard
    agent_card_url: str

    @property
    def agent_card_route(self) -> str:
        """Return the server-root route on which the public Agent Card is served."""

        return urlparse(self.agent_card_url).path


class A2AServerConfigurationService:
    """Load external A2A server configuration and the official Agent Card."""

    def __init__(
        self,
        loader: A2AServerConfigurationLoader | None = None,
        factory: A2AAgentCardFactory | None = None,
    ) -> None:
        """Create the service with replaceable loading and construction components."""

        self._loader = loader or A2AServerConfigurationLoader()
        self._factory = factory or A2AAgentCardFactory()

    def load(self, path: Path) -> A2AServerConfiguration:
        """Load publication settings and construct one official A2A Agent Card."""

        configuration = self._loader.load(path)
        agent_card_url = configuration.pop("url", None)
        if not isinstance(agent_card_url, str) or not agent_card_url.strip():
            raise ConfigurationError(
                "A2A server agent_card.url must be a non-empty absolute HTTP(S) URL"
            )
        agent_card_url = agent_card_url.strip()
        parsed = urlparse(agent_card_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or not parsed.path.startswith("/")
            or parsed.query
            or parsed.fragment
        ):
            raise ConfigurationError(
                "A2A server agent_card.url must be an absolute HTTP(S) URL without query or fragment",
                details={"value": agent_card_url},
            )
        return A2AServerConfiguration(
            agent_card=self._factory.create(configuration),
            agent_card_url=agent_card_url,
        )

    def load_agent_card(self, path: Path) -> AgentCard:
        """Load only the official Agent Card for compatibility with existing callers."""

        return self.load(path).agent_card
