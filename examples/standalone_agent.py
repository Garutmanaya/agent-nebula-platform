"""Standalone preset example for a new Agent Studio-style agent.

The example intentionally omits OAuth service construction. Production agents
must compose those services from ``agent-nebula-sdk`` and inject them through
``RuntimeFeatureComponents``.
"""

from __future__ import annotations

from pathlib import Path

from agent_nebula_platform.agent_card import StaticAgentCardProvider
from agent_nebula_platform.platform.health import StaticHealthProvider
from agent_nebula_platform.platform.presets import (
    RuntimeFeatureComponents,
    StandaloneRuntimeSettings,
    build_standalone_agent,
)


def main() -> None:
    """Load standalone infrastructure and run the HTTPS agent process."""

    settings = StandaloneRuntimeSettings.from_ini(
        Path("application.conf")
    )
    components = RuntimeFeatureComponents.create(
        agent_card=StaticAgentCardProvider(
            {
                "name": "Example Agent",
                "version": "1.0.0",
                "protocols": ["A2A"],
            }
        ),
        health=StaticHealthProvider(),
    )
    build_standalone_agent(
        settings=settings,
        components=components,
    ).run()


if __name__ == "__main__":
    main()
