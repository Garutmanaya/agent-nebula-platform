import pytest

from agent_nebula_platform import (
    AgentRuntime,
    MemoryStateStore,
    NullEventSink,
    RuntimeContext,
)
from agent_nebula_platform.platform.plugins import RuntimePlugin


class Connector:
    async def close(self):
        pass


class Plugin(RuntimePlugin):
    def __init__(self, name, events, required=True, fail=False):
        self._name = name
        self.events = events
        self._required = required
        self.fail = fail

    @property
    def name(self):
        return self._name

    @property
    def required(self):
        return self._required

    async def initialize(self, context):
        self.events.append("init:" + self.name)
        if self.fail:
            raise RuntimeError("boom")

    async def close(self, context):
        self.events.append("close:" + self.name)


@pytest.mark.asyncio
async def test_plugins_start_and_close_in_reverse_order():
    events = []
    ctx = RuntimeContext(
        nebula=Connector(), state_store=MemoryStateStore(), events=NullEventSink()
    )
    runtime = AgentRuntime(
        context=ctx, plugins=[Plugin("a", events), Plugin("b", events)]
    )
    await runtime.initialize()
    await runtime.close()
    assert events == ["init:a", "init:b", "close:b", "close:a"]


@pytest.mark.asyncio
async def test_optional_plugin_failure_does_not_fail_runtime():
    events = []
    ctx = RuntimeContext(
        nebula=Connector(), state_store=MemoryStateStore(), events=NullEventSink()
    )
    runtime = AgentRuntime(
        context=ctx,
        plugins=[
            Plugin("optional", events, required=False, fail=True),
            Plugin("required", events),
        ],
    )
    await runtime.initialize()
    await runtime.close()
    assert "init:required" in events


@pytest.mark.asyncio
async def test_plugin_lifecycle_hooks_wrap_initialize_and_close() -> None:
    """Lifecycle hooks execute in deterministic order around plugin ownership."""

    events: list[str] = []

    class HookPlugin(RuntimePlugin):
        """Record every lifecycle phase for ordering verification."""

        @property
        def name(self) -> str:
            """Return the stable test plugin name."""

            return "hooks"

        async def before_start(self, context: RuntimeContext) -> None:
            """Record pre-start execution."""

            del context
            events.append("before_start")

        async def initialize(self, context: RuntimeContext) -> None:
            """Record initialization execution."""

            del context
            events.append("initialize")

        async def after_start(self, context: RuntimeContext) -> None:
            """Record post-start execution."""

            del context
            events.append("after_start")

        async def before_shutdown(self, context: RuntimeContext) -> None:
            """Record pre-shutdown execution."""

            del context
            events.append("before_shutdown")

        async def close(self, context: RuntimeContext) -> None:
            """Record close execution."""

            del context
            events.append("close")

        async def after_shutdown(self, context: RuntimeContext) -> None:
            """Record final shutdown execution."""

            del context
            events.append("after_shutdown")

    context = RuntimeContext(
        nebula=Connector(),
        state_store=MemoryStateStore(),
        events=NullEventSink(),
    )
    runtime = AgentRuntime(context=context, plugins=(HookPlugin(),))

    await runtime.initialize()
    await runtime.close()

    assert events == [
        "before_start",
        "initialize",
        "after_start",
        "before_shutdown",
        "close",
        "after_shutdown",
    ]
