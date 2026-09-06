# A2UI Skill Result Example

```python
surface = A2UISurface(
    surface_id="flight-results",
    messages=(
        A2UIMessage(document={
            "version": "v0.9.1",
            "createSurface": {
                "surfaceId": "flight-results",
                "catalogId": "urn:agent-nebula:a2ui:travel",
            },
        }),
        A2UIMessage(document={
            "version": "v0.9.1",
            "updateComponents": {
                "surfaceId": "flight-results",
                "components": [
                    {"id": "root", "component": "Column", "children": ["title"]},
                    {"id": "title", "component": "Text", "text": "Flights"},
                ],
            },
        }),
    ),
)
return SkillResult(data={"flights": []}, ui=surface)
```

Configure an approved component catalog and explicit action-to-skill bindings. See [A2UI plugin](../plugins/a2ui.md) and [A2UI security](../security/a2ui.md).
