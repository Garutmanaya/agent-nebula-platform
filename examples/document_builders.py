"""Build authoritative Agent Card and Protected Resource Metadata documents."""

from __future__ import annotations

from agent_nebula_platform.agent_card import AgentCardBuilder, AgentSkillDescriptor
from agent_nebula_platform.security.oauth.metadata import ProtectedResourceMetadataBuilder


def build_documents() -> tuple[dict[str, object], dict[str, object]]:
    """Return complete travel-agent discovery and OAuth metadata documents."""

    agent_card = (
        AgentCardBuilder()
        .identity(
            external_agent_id="airline-booking-agent",
            display_name="Airline Booking Agent",
            description="Search and reserve configured demonstration flights.",
            version="1.0.0",
        )
        .roles(("A2A_PROVIDER", "OAUTH_PROTECTED_RESOURCE"))
        .protocols(("A2A", "A2UI"))
        .capabilities(("travel", "airline-booking"))
        .endpoints(
            {
                "health": "https://airline.example.test/health",
                "a2a": "https://airline.example.test/a2a",
                "agent_card": (
                    "https://airline.example.test/.well-known/agent-card.json"
                ),
            }
        )
        .skills(
            (
                AgentSkillDescriptor(
                    id="airline.search",
                    name="Search flights",
                    required_scopes=("airline.search",),
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                    extensions={"a2ui": {"surface": "flight-results"}},
                ),
            )
        )
        .build()
    )

    protected_resource = (
        ProtectedResourceMetadataBuilder()
        .resource("https://airline.example.test")
        .authorization_servers(("https://nebula.example.test",))
        .scopes_supported(("airline.search",))
        .bearer_methods(("header",))
        .dpop(required=True, algorithms=("ES256",))
        .details(resource_name="Airline Booking Agent")
        .build()
    )

    return agent_card.copy_document(), protected_resource.copy_document()
