"""Tests for the ``sensai.agent`` module."""

import json
import re
from typing import Any

import pytest

from sensai.agent import Agent
from sensai.client import OllamaClient, Response
from sensai.data.session.message import Message
from sensai.react import FINAL_ANSWER
from sensai.ui.protocol import AsyncUIHandler

TEST_BASE_URL = "http://localhost:11434/api/chat"
TEST_TOKEN = "test-token"  # noqa: S105
TEST_TIMEOUT = 30.0


def _make_response(response: str = "") -> Response:
    return Response(
        response=response,
        respond_time=0.0,
        request_time=0.0,
        total_duration=0,
        model="llama3.2",
        tools=[],
        messages=[],
        prompt_eval_count=0,
        eval_count=0,
        token_used=0,
        status_code=200,
        tool_calls=[],
        stop_reason="stop",
    )


def _step(
    action: str,
    args: dict[str, Any] | None = None,
    thought: str = "thinking",
    missing: str | None = None,
) -> str:
    if missing is None:
        missing = "nothing" if action == FINAL_ANSWER else "the result"
    return json.dumps(
        {"thought": thought, "missing": missing, "action": action, "args": args or {}}
    )


class ScriptedClient(OllamaClient):
    """Mock client replaying planning steps in order, then answering with ``answer``.

    Planning calls are told apart by their ``response_format``; once the script is used
    up, every planning call picks the final answer.
    """

    def __init__(self, steps: list[str] | None = None, answer: str = "Hello!") -> None:
        """Initialize the mock with the planning replies and the final answer."""
        super().__init__(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)
        self.steps = list(steps or [])
        self.answer = answer
        self.plans: list[dict[str, Any]] = []
        self.answers: list[dict[str, Any]] = []

    async def chat(self, messages: list[dict[str, Any]], *_args: Any, **kwargs: Any) -> Response:
        call = {"messages": messages, **kwargs}
        if kwargs.get("response_format") is not None:
            self.plans.append(call)
            return _make_response(self.steps.pop(0) if self.steps else _step(FINAL_ANSWER))
        self.answers.append(call)
        response = _make_response(self.answer)
        response.messages = [
            Message(role=m["role"], content=m["content"], response_time=0.0) for m in messages
        ]
        response.messages.append(Message(role="assistant", content=self.answer, response_time=0.0))
        return response


class MockUIHandler(AsyncUIHandler):
    """Mock UI Handler for testing Agent."""

    def __init__(self, *, approval: bool = True) -> None:
        """Initialize the mock UI handler."""
        self.streamed: list[str] = []
        self.tool_requests: list[tuple[str, dict[str, Any]]] = []
        self.tool_results: list[tuple[str, Any]] = []
        self.errors: list[Exception] = []
        self.thinking: list[str] = []
        self.approval = approval

    async def on_stream_chunk(self, chunk: str) -> None:
        self.streamed.append(chunk)

    async def on_tool_call_request(self, name: str, arguments: dict[str, Any]) -> bool:
        self.tool_requests.append((name, arguments))
        return self.approval

    async def on_tool_call_result(self, name: str, result: Any) -> None:
        self.tool_results.append((name, result))

    async def on_error(self, error: Exception) -> None:
        self.errors.append(error)

    async def on_thinking_chunk(self, chunk: str) -> None:
        self.thinking.append(chunk)

    async def on_system_message(self, message: Any) -> None:
        pass


class FakeTool:
    """Fake tool for agent tests."""

    name = "calculator"

    def define(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "Compute an expression.",
                "parameters": {
                    "type": "object",
                    "required": ["expr"],
                    "properties": {"expr": {"type": "string"}},
                },
            },
        }

    def execute(self, **kwargs: Any) -> str:
        return f"result: {kwargs.get('expr')}"


class AsyncFakeTool(FakeTool):
    """Fake async tool for testing coroutine execution."""

    name = "async_calculator"

    def define(self) -> dict[str, Any]:
        definition = super().define()
        definition["function"]["name"] = "async_calculator"
        return definition

    async def execute(self, **kwargs: Any) -> str:  # type: ignore[override]
        return f"async result: {kwargs.get('expr')}"


class BrokenTool(FakeTool):
    """Fake tool that always raises."""

    name = "broken"

    def define(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": "broken"}}

    def execute(self, **kwargs: Any) -> str:  # noqa: ARG002
        raise RuntimeError("Tool execution failed unexpectedly")


def _system_texts(call: dict[str, Any]) -> str:
    return "\n".join(m["content"] for m in call["messages"] if m["role"] == "system")


@pytest.mark.asyncio
async def test_agent_missing_input() -> None:
    agent = Agent(client=ScriptedClient())
    pattern = re.escape("Either prompt or messages must be provided.")
    with pytest.raises(ValueError, match=pattern):
        await agent.run()


@pytest.mark.asyncio
async def test_agent_rejects_non_positive_max_turns() -> None:
    agent = Agent(client=ScriptedClient())
    agent.max_turns = 0
    with pytest.raises(ValueError, match="max_turns must be at least 1"):
        await agent.run("Hi")


@pytest.mark.asyncio
async def test_agent_answers_directly_without_tools() -> None:
    client = ScriptedClient(answer="Hello!")
    ui = MockUIHandler()
    agent = Agent(client=client, ui_handler=ui)

    result = await agent.run("Hi")

    assert result.response == "Hello!"
    assert len(client.plans) == 1
    assert len(client.answers) == 1
    assert client.answers[0]["tools"] == []
    assert ui.thinking == ["thinking\n\n"]
    assert [(m.role, m.content) for m in result.messages] == [
        ("user", "Hi"),
        ("assistant", "Hello!"),
    ]


@pytest.mark.asyncio
async def test_agent_system_prompt_injection() -> None:
    client = ScriptedClient()
    agent = Agent(client=client)
    agent.system_prompt = "You are a helpful assistant."

    await agent.run("Hello")

    assert client.answers[0]["messages"] == [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
    ]


@pytest.mark.asyncio
async def test_agent_system_prompt_not_duplicated() -> None:
    client = ScriptedClient()
    agent = Agent(client=client)
    existing = [
        {"role": "system", "content": "Custom system prompt."},
        {"role": "user", "content": "Hi"},
    ]

    await agent.run(messages=existing, system_prompt="Different system prompt")

    assert client.answers[0]["messages"] == existing


@pytest.mark.asyncio
async def test_agent_plan_is_constrained_and_never_sent_as_user() -> None:
    client = ScriptedClient()
    agent = Agent(tools=[FakeTool()], client=client)

    await agent.run("Hi")

    plan = client.plans[0]
    assert plan["tools"] == []
    assert plan["options"] == {"temperature": 0}
    assert plan["response_format"]["properties"]["action"]["enum"] == ["calculator", FINAL_ANSWER]
    assert plan["messages"][-1]["role"] == "system"
    assert [m for m in plan["messages"] if m["role"] == "user"] == [
        {"role": "user", "content": "Hi"}
    ]


@pytest.mark.asyncio
async def test_agent_runs_tool_then_answers_with_its_result() -> None:
    client = ScriptedClient(steps=[_step("calculator", {"expr": "2+2"})], answer="The answer is 4.")
    ui = MockUIHandler(approval=True)
    agent = Agent(tools=[FakeTool()], human_in_the_loop=True, ui_handler=ui, client=client)

    result = await agent.run("What is 2+2?")

    assert result.response == "The answer is 4."
    assert ui.tool_requests == [("calculator", {"expr": "2+2"})]
    assert ui.tool_results == [("calculator", "result: 2+2")]
    assert len(client.plans) == 2
    assert "result: 2+2" in client.plans[1]["messages"][-1]["content"]
    assert "result: 2+2" in _system_texts(client.answers[0])
    assert [(m.role, m.content) for m in result.messages] == [
        ("user", "What is 2+2?"),
        ("assistant", "The answer is 4."),
    ]


@pytest.mark.asyncio
async def test_agent_async_tool_execution() -> None:
    client = ScriptedClient(steps=[_step("async_calculator", {"expr": "3+3"})])
    ui = MockUIHandler()
    agent = Agent(tools=[AsyncFakeTool()], ui_handler=ui, client=client)

    await agent.run("What is 3+3?")

    assert ui.tool_results == [("async_calculator", "async result: 3+3")]


@pytest.mark.asyncio
async def test_agent_tool_denied_by_user() -> None:
    client = ScriptedClient(steps=[_step("calculator", {"expr": "2+2"})])
    ui = MockUIHandler(approval=False)
    agent = Agent(tools=[FakeTool()], human_in_the_loop=True, ui_handler=ui, client=client)

    await agent.run("What is 2+2?")

    assert ui.tool_results == []
    assert "The user refused this action." in client.plans[1]["messages"][-1]["content"]
    assert len(client.answers[0]["messages"]) == 1


@pytest.mark.asyncio
async def test_agent_rejects_invalid_step_without_running_it() -> None:
    client = ScriptedClient(steps=[_step("unknown"), _step("calculator", {})])
    ui = MockUIHandler()
    agent = Agent(tools=[FakeTool()], human_in_the_loop=True, ui_handler=ui, client=client)

    await agent.run("Hi")

    assert ui.tool_requests == []
    planning = client.plans[2]["messages"][-1]["content"]
    assert "'unknown' is not available now" in planning
    assert "missing argument(s): expr" in planning


@pytest.mark.asyncio
async def test_agent_rejects_repeated_call() -> None:
    call = _step("calculator", {"expr": "2+2"})
    client = ScriptedClient(steps=[call, call])
    ui = MockUIHandler()
    agent = Agent(tools=[FakeTool()], ui_handler=ui, client=client)

    await agent.run("What is 2+2?")

    assert ui.tool_results == [("calculator", "result: 2+2")]
    assert "already made at step 1" in client.plans[2]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_agent_tool_error_becomes_observation() -> None:
    client = ScriptedClient(steps=[_step("broken")], answer="Sorry.")
    ui = MockUIHandler()
    agent = Agent(tools=[BrokenTool()], ui_handler=ui, client=client)

    result = await agent.run("hello")

    assert result.response == "Sorry."
    assert [str(e) for e in ui.errors] == ["Tool execution failed unexpectedly"]
    assert "Error: Tool execution failed unexpectedly" in client.plans[1]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_agent_error_notifies_ui() -> None:
    class MockClient(OllamaClient):
        async def chat(self, *_args: Any, **_kwargs: Any) -> Response:
            raise RuntimeError("API crash")

    ui = MockUIHandler()
    agent = Agent(
        ui_handler=ui,
        client=MockClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT),
    )

    with pytest.raises(RuntimeError, match="API crash"):
        await agent.run("hello")

    assert [str(e) for e in ui.errors] == ["API crash"]


@pytest.mark.asyncio
async def test_agent_stops_planning_after_max_turns() -> None:
    client = ScriptedClient(
        steps=[_step("calculator", {"expr": str(n)}) for n in range(10)], answer="Done."
    )
    agent = Agent(tools=[FakeTool()], client=client)
    agent.max_turns = 2

    result = await agent.run("loop")

    assert len(client.plans) == 2
    assert len(client.answers) == 1
    assert result.response == "Done."


@pytest.mark.asyncio
async def test_agent_unreadable_plan_falls_back_to_answer() -> None:
    client = ScriptedClient(steps=["not json"], answer="Hi there.")
    agent = Agent(tools=[FakeTool()], client=client)

    result = await agent.run("Hi")

    assert len(client.plans) == 1
    assert result.response == "Hi there."


@pytest.mark.asyncio
async def test_agent_stops_when_nothing_is_missing_and_keeps_thought_as_draft() -> None:
    client = ScriptedClient(
        steps=[
            _step("calculator", {"expr": "2+2"}),
            _step("calculator", {"expr": "2*2"}, thought="It is 4.", missing="nothing"),
        ],
        answer="4.",
    )
    ui = MockUIHandler()
    agent = Agent(tools=[FakeTool()], ui_handler=ui, client=client)

    await agent.run("What is 2+2?")

    assert ui.tool_results == [("calculator", "result: 2+2")]
    assert len(client.plans) == 2
    notes = _system_texts(client.answers[0])
    assert "result: 2+2" in notes
    assert "It is 4." in notes


@pytest.mark.asyncio
async def test_agent_drops_undeclared_arguments() -> None:
    client = ScriptedClient(steps=[_step("calculator", {"expr": "2+2", "thought": "copied"})])
    ui = MockUIHandler()
    agent = Agent(tools=[FakeTool()], human_in_the_loop=True, ui_handler=ui, client=client)

    await agent.run("What is 2+2?")

    assert ui.tool_requests == [("calculator", {"expr": "2+2"})]
