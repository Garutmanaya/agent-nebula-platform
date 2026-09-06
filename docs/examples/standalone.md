# Standalone Composition Example

Standalone mode is intended for Agent Studio and greenfield agents.

```python
settings = StandaloneRuntimeSettings.from_sources()
components = RuntimeFeatureComponents.create(
    skill_definitions=skills,
    agent_card=agent_card_provider,
    protected_resource_metadata=resource_metadata_provider,
    health=health_provider,
    metrics_registry=metrics,
    telemetry_sinks=(telemetry_sink,),
    scheduled_jobs=jobs,
    oauth_client=oauth_client_service,
    protected_resource=protected_resource_service,
)
agent = build_standalone_agent(settings=settings, components=components)
agent.run()
```

The caller still supplies business skills, authoritative documents, credentials, and SDK-composed OAuth services. The preset supplies infrastructure ownership selected by configuration.
