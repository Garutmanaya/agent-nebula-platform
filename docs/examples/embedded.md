# Embedded Composition Example

```python
runtime = build_embedded_runtime(
    context=RuntimeContext(
        nebula=nebula_connector,
        state_store=existing_state_adapter,
        events=existing_event_sink,
    ),
    components=RuntimeFeatureComponents.create(
        skill_definitions=skills,
        protected_resource=protected_resource_service,
        agent_card=agent_card_provider,
    ),
    options=EmbeddedPresetOptions(app=existing_fastapi_app),
)
```

Initialize and close the runtime through the host's existing lifespan. The runtime does not start Uvicorn or configure global logging in this mode.
