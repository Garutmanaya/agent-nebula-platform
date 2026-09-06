# Implementing a Custom Plugin

```python
from agent_runtime.health import HealthStatus
from agent_runtime.plugins import RuntimePlugin

class ExamplePlugin(RuntimePlugin):
    @property
    def name(self) -> str:
        return "example.capability"

    @property
    def required(self) -> bool:
        return False

    async def initialize(self, context) -> None:
        context.services.register("example", object())

    async def close(self, context) -> None:
        ...

    async def health(self) -> HealthStatus:
        return HealthStatus(status="healthy", ready=True)
```

Guidelines:

- use a stable unique plugin name;
- depend on ports or registered services, not another plugin's implementation internals;
- register services during initialization;
- release resources during close;
- emit stable non-secret events;
- return actionable health without exposing internals;
- document required ordering;
- add lifecycle, rollback, health, and negative tests.
