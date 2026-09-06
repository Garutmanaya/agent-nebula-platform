# Migrating an Existing FastAPI Agent

Use the embedded preset.

```python
from contextlib import asynccontextmanager

runtime = build_embedded_runtime(
    context=context,
    components=components,
    options=EmbeddedPresetOptions(app=app),
)

@asynccontextmanager
async def lifespan(app):
    await runtime.initialize()
    try:
        yield
    finally:
        await runtime.close()
```

The host retains:

- existing middleware;
- exception handlers;
- unrelated routes;
- Uvicorn/Gunicorn process model;
- logging;
- database lifecycle.

Runtime route attachment is opt-in and should avoid collisions with existing paths.
