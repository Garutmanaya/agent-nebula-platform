"""Checkpoint 11.5 tests for the first-class A2UI session engine."""

from __future__ import annotations

import pytest

from agent_nebula_platform.a2ui.session import (
    A2UIActionRecord,
    A2UISessionService,
    A2UISurfaceFrame,
    A2UISurfaceMode,
    MemoryA2UISessionStore,
)
from agent_nebula_platform.platform.events import NullEventSink


@pytest.mark.asyncio
async def test_session_engine_manages_navigation_data_actions_and_participants() -> (
    None
):
    service = A2UISessionService(
        store=MemoryA2UISessionStore(),
        events=NullEventSink(),
        max_history=10,
    )
    session = await service.create(renderer={"supported_versions": ["v0.9.1"]})
    session = await service.select_agent(session.session_id, "parking-agent")
    session = await service.apply_surface(
        session.session_id,
        A2UISurfaceFrame(
            surface_id="search-results",
            owner_agent_id="parking-agent",
            skill_id="parking.search",
            messages=(
                {"version": "v0.9.1", "createSurface": {"surfaceId": "search-results"}},
            ),
        ),
    )
    session = await service.apply_surface(
        session.session_id,
        A2UISurfaceFrame(
            surface_id="garage-layout",
            owner_agent_id="parking-agent",
            skill_id="parking.layout",
        ),
    )
    assert session.current_surface is not None
    assert session.current_surface.surface_id == "garage-layout"
    assert session.participant_agent_ids == ("parking-agent",)
    session = await service.back(session.session_id)
    assert session.current_surface is not None
    assert session.current_surface.surface_id == "search-results"
    session = await service.forward(session.session_id)
    assert session.current_surface is not None
    assert session.current_surface.surface_id == "garage-layout"
    session = await service.update_data_model(
        session.session_id,
        {"parking": {"slot": "L1-01", "hold": {"status": "PENDING"}}},
    )
    session = await service.update_data_model(
        session.session_id,
        {"parking": {"hold": {"status": "HELD"}}},
    )
    assert session.data_model["parking"]["slot"] == "L1-01"
    assert session.data_model["parking"]["hold"]["status"] == "HELD"
    session = await service.record_action(
        session.session_id,
        A2UIActionRecord(
            name="parking.hold",
            surface_id="garage-layout",
            owner_agent_id="parking-agent",
        ),
    )
    assert session.actions[-1].name == "parking.hold"


@pytest.mark.asyncio
async def test_surface_replace_and_append_are_deterministic() -> None:
    service = A2UISessionService(
        store=MemoryA2UISessionStore(),
        events=NullEventSink(),
    )
    session = await service.create(renderer={})
    session = await service.apply_surface(
        session.session_id,
        A2UISurfaceFrame(surface_id="one", owner_agent_id="a", skill_id="s"),
    )
    session = await service.apply_surface(
        session.session_id,
        A2UISurfaceFrame(
            surface_id="one",
            owner_agent_id="a",
            skill_id="s",
            mode=A2UISurfaceMode.REPLACE,
            data={"value": 1},
        ),
    )
    assert len(session.surfaces) == 1
    assert session.current_surface is not None
    assert session.current_surface.data == {"value": 1}
    session = await service.apply_surface(
        session.session_id,
        A2UISurfaceFrame(
            surface_id="one",
            owner_agent_id="a",
            skill_id="s",
            mode=A2UISurfaceMode.APPEND,
            data={"next": 2},
        ),
    )
    assert session.current_surface is not None
    assert session.current_surface.data == {"value": 1, "next": 2}


@pytest.mark.asyncio
async def test_json_session_store_survives_service_recreation(tmp_path) -> None:
    """Persisted session state can be resumed after process reconstruction."""

    from agent_nebula_platform.a2ui.session import JsonFileA2UISessionStore

    first = A2UISessionService(
        store=JsonFileA2UISessionStore(tmp_path),
        events=NullEventSink(),
    )
    session = await first.create(renderer={"supported_versions": ["v0.9.1"]})
    session = await first.select_agent(session.session_id, "finance-agent")
    session = await first.apply_surface(
        session.session_id,
        A2UISurfaceFrame(
            surface_id="portfolio",
            owner_agent_id="finance-agent",
            skill_id="finance.portfolio.read",
            data={"portfolio_id": "P-1"},
        ),
    )

    second = A2UISessionService(
        store=JsonFileA2UISessionStore(tmp_path),
        events=NullEventSink(),
    )
    restored = await second.get(session.session_id)

    assert restored.selected_agent_id == "finance-agent"
    assert restored.current_surface is not None
    assert restored.current_surface.surface_id == "portfolio"
    assert restored.current_surface.data == {"portfolio_id": "P-1"}
