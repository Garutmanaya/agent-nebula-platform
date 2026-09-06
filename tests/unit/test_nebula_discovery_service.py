from pathlib import Path

from agent_nebula_platform.integrations.nebula.discovery_service import (
    NebulaDiscoveryServiceFactory,
)


def test_discovery_factory_loads_nebula_configuration(monkeypatch) -> None:
    captured = {}

    class _Configuration:
        pass

    class _Service:
        def __init__(self, configuration):
            captured["configuration"] = configuration

    monkeypatch.setattr(
        "agent_nebula_platform.integrations.nebula.discovery_service.NebulaConfiguration.load",
        lambda path: _Configuration(),
    )
    monkeypatch.setattr(
        "agent_nebula_platform.integrations.nebula.discovery_service.NebulaDiscoveryService",
        _Service,
    )

    service = NebulaDiscoveryServiceFactory.create(Path("nebula.conf"))

    assert isinstance(service, _Service)
    assert isinstance(captured["configuration"], _Configuration)
