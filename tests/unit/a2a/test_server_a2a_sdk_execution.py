from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest
from a2a.server.agent_execution import AgentExecutor

from agent_nebula_platform.platform.errors import ConfigurationError
from agent_nebula_platform.protocols.a2a.server_a2a_sdk.execution import A2ASdkAgentExecutor


@dataclass(frozen=True)
class _Skill:
    skill_id: str
    executor: AgentExecutor
    schema_contract_id: str | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None


class _Executor(AgentExecutor):
    def __init__(self):
        self.execute = AsyncMock()
        self.cancel = AsyncMock()


class _Context:
    def __init__(self, *, task_id="task-1", metadata=None, requested_extensions=None):
        self.message = None
        self.task_id = task_id
        self.metadata = metadata or {}
        self.requested_extensions = requested_extensions or set()


@pytest.mark.asyncio
async def test_single_skill_receives_native_context_and_event_queue_unchanged():
    application = _Executor()
    dispatcher = A2ASdkAgentExecutor((_Skill("report", application),))
    context = _Context()
    queue = object()

    await dispatcher.execute(context, queue)

    application.execute.assert_awaited_once_with(context, queue)


@pytest.mark.asyncio
async def test_multi_skill_requires_explicit_nebula_selection():
    dispatcher = A2ASdkAgentExecutor(
        (_Skill("one", _Executor()), _Skill("two", _Executor()))
    )

    with pytest.raises(ConfigurationError, match="skill-selection"):
        await dispatcher.execute(_Context(), object())


@pytest.mark.asyncio
async def test_cancel_is_dispatched_to_executor_selected_for_task(monkeypatch):
    one = _Executor()
    two = _Executor()
    dispatcher = A2ASdkAgentExecutor((_Skill("one", one), _Skill("two", two)))
    context = _Context(task_id="task-7")
    queue = object()

    monkeypatch.setattr(
        "agent_nebula_platform.protocols.a2a.server_a2a_sdk.execution.selected_skill_id",
        lambda **_: "two",
    )
    await dispatcher.execute(context, queue)
    await dispatcher.cancel(_Context(task_id="task-7"), queue)

    two.execute.assert_awaited_once_with(context, queue)
    two.cancel.assert_awaited_once()
    one.execute.assert_not_awaited()
