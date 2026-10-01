"""Tests for the ``sensai.agent`` module."""

import re
from typing import Any

import pytest

from sensai.agent import THINK_PROMPT, Agent
from sensai.client import OllamaClient, Response
from sensai.data.session.message import Message
from sensai.ui.protocol import AsyncUIHandler

TEST_BASE_URL = "http://localhost:11434/api/chat"
TEST_TOKEN = "test-token"  # noqa: S105
TEST_TIMEOUT = 30.0
THINK_PREFIX = THINK_PROMPT.split("{", maxsplit=1)[0]


def _make_response(response: str = "", tool_calls: list[dict[str, Any]] | None = None) -> Response:
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
        tool_calls=tool_calls or [],
        stop_reason="stop",
    )


def _reasoning_reply(messages: list[dict[str, Any]], kwargs: dict[str, Any]) -> Response | None:
    """Default reply to the agent's THINK and CHECK calls, or None for an ACT call."""
    if messages and messages[-1]["content"].startswith(THINK_PREFIX):
        return _make_response("thought")
    if kwargs.get("stream") is False:
        return _make_response("YES")
    return None


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
        return {"type": "function", "function": {"name": "calculator"}}

    def execute(self, **kwargs: Any) -> str:
        return f"result: {kwargs.get('expr')}"


class AsyncFakeTool:
    """Fake async tool for testing coroutine execution."""

    name = "async_calculator"

    def define(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": "async_calculator"}}

    async def execute(self, **kwargs: Any) -> str:
        return f"async result: {kwargs.get('expr')}"


@pytest.mark.asyncio
async def test_agent_missing_input() -> None:
    agent = Agent(
        client=OllamaClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)
    )
    pattern = re.escape("Either prompt or messages must be provided.")
    with pytest.raises(ValueError, match=pattern):
        await agent.run()


@pytest.mark.asyncio
async def test_agent_system_prompt_injection() -> None:
    captured: dict[str, Any] = {}

    class MockClient(OllamaClient):
        async def chat(
            self, messages: list[dict[str, Any]], *_args: Any, **kwargs: Any
        ) -> Response:
            if (reply := _reasoning_reply(messages, kwargs)) is not None:
                return reply
            captured["messages"] = messages
            return _make_response("ok")

    agent = Agent(client=MockClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT))
    agent.system_prompt = "You are a helpful assistant."
    await agent.run("Hello")

    assert captured["messages"][:2] == [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
    ]


@pytest.mark.asyncio
async def test_agent_system_prompt_not_duplicated() -> None:
    captured: dict[str, Any] = {}

    class MockClient(OllamaClient):
        async def chat(
            self, messages: list[dict[str, Any]], *_args: Any, **kwargs: Any
        ) -> Response:
            if (reply := _reasoning_reply(messages, kwargs)) is not None:
                return reply
            captured["messages"] = messages
            return _make_response("ok")

    agent = Agent(client=MockClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT))
    existing = [
        {"role": "system", "content": "Custom system prompt."},
        {"role": "user", "content": "Hi"},
    ]
    await agent.run(messages=existing, system_prompt="Different system prompt")

    # system + user + the ephemeral ACT instruction carrying the thought
    assert len(captured["messages"]) == 3
    assert captured["messages"][0]["content"] == "Custom system prompt."


@pytest.mark.asyncio
async def test_agent_tool_loop_and_execution() -> None:
    turns = 0

    class MockClient(OllamaClient):
        async def chat(
            self, messages: list[dict[str, Any]], *_args: Any, **kwargs: Any
        ) -> Response:
            if (reply := _reasoning_reply(messages, kwargs)) is not None:
                return reply
            nonlocal turns
            turns += 1
            if turns == 1:
                return _make_response(
                    tool_calls=[{"function": {"name": "calculator", "arguments": {"expr": "2+2"}}}],
                )
            return _make_response("The answer is 4.")

    ui = MockUIHandler(approval=True)
    tool = FakeTool()
    agent = Agent(
        tools=[tool],
        human_in_the_loop=True,
        ui_handler=ui,
        client=MockClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT),
    )

    result = await agent.run("What is 2+2?")

    assert result.response == "The answer is 4."
    assert turns == 2
    assert len(ui.tool_requests) == 1
    assert ui.tool_requests[0] == ("calculator", {"expr": "2+2"})
    assert len(ui.tool_results) == 1
    assert ui.tool_results[0] == ("calculator", "result: 2+2")


@pytest.mark.asyncio
async def test_agent_async_tool_execution() -> None:
    turns = 0

    class MockClient(OllamaClient):
        async def chat(
            self, messages: list[dict[str, Any]], *_args: Any, **kwargs: Any
        ) -> Response:
            if (reply := _reasoning_reply(messages, kwargs)) is not None:
                return reply
            nonlocal turns
            turns += 1
            if turns == 1:
                return _make_response(
                    tool_calls=[
                        {"function": {"name": "async_calculator", "arguments": {"expr": "3+3"}}}
                    ],
                )
            return _make_response("The answer is 6.")

    ui = MockUIHandler(approval=True)
    tool = AsyncFakeTool()
    agent = Agent(
        tools=[tool],
        human_in_the_loop=False,
        ui_handler=ui,
        client=MockClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT),
    )

    result = await agent.run("What is 3+3?")

    assert result.response == "The answer is 6."
    assert len(ui.tool_results) == 1
    assert ui.tool_results[0] == ("async_calculator", "async result: 3+3")


@pytest.mark.asyncio
async def test_agent_tool_denied_by_user() -> None:
    turns = 0
    captured_messages: list[dict[str, Any]] = []

    class MockClient(OllamaClient):
        async def chat(
            self, messages: list[dict[str, Any]], *_args: Any, **kwargs: Any
        ) -> Response:
            if (reply := _reasoning_reply(messages, kwargs)) is not None:
                return reply
            nonlocal turns
            turns += 1
            if turns == 1:
                return _make_response(
                    tool_calls=[{"function": {"name": "calculator", "arguments": {"expr": "2+2"}}}],
                )
            captured_messages.extend(messages)
            return _make_response("Operation cancelled.")

    ui = MockUIHandler(approval=False)
    tool = FakeTool()
    agent = Agent(
        tools=[tool],
        human_in_the_loop=True,
        ui_handler=ui,
        client=MockClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT),
    )

    result = await agent.run("What is 2+2?")

    assert result.response == "Operation cancelled."
    assert len(ui.tool_results) == 0
    # [-1] is the ephemeral ACT instruction, the tool result comes right before it
    assert captured_messages[-2] == {
        "role": "tool",
        "content": "Action cancelled by user.",
        "tool_name": "calculator",
    }


@pytest.mark.asyncio
async def test_agent_tool_not_found() -> None:
    turns = 0
    captured_messages: list[dict[str, Any]] = []

    class MockClient(OllamaClient):
        async def chat(
            self, messages: list[dict[str, Any]], *_args: Any, **kwargs: Any
        ) -> Response:
            if (reply := _reasoning_reply(messages, kwargs)) is not None:
                return reply
            nonlocal turns
            turns += 1
            if turns == 1:
                return _make_response(
                    tool_calls=[{"function": {"name": "unknown", "arguments": {}}}],
                )
            captured_messages.extend(messages)
            return _make_response("Fixed.")

    agent = Agent(
        tools=[], client=MockClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)
    )
    result = await agent.run("Run unknown tool")

    assert result.response == "Fixed."
    assert captured_messages[-2] == {
        "role": "tool",
        "content": "Tool 'unknown' not found.",
        "tool_name": "unknown",
    }


@pytest.mark.asyncio
async def test_agent_tool_error_notifies_ui_and_raises() -> None:
    class BrokenTool:
        name = "broken"

        def define(self) -> dict[str, Any]:
            return {"type": "function", "function": {"name": "broken"}}

        def execute(self, **kwargs: Any) -> str:  # noqa: ARG002
            raise RuntimeError("Tool execution failed unexpectedly")

    class MockClient(OllamaClient):
        async def chat(self, *_args: Any, **_kwargs: Any) -> Response:
            return _make_response(
                tool_calls=[{"function": {"name": "broken", "arguments": {}}}],
            )

    ui = MockUIHandler()
    agent = Agent(
        tools=[BrokenTool()],
        ui_handler=ui,
        client=MockClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT),
    )

    with pytest.raises(RuntimeError, match="Tool execution failed unexpectedly"):
        await agent.run("hello")

    assert len(ui.errors) == 1
    assert str(ui.errors[0]) == "Tool execution failed unexpectedly"


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

    assert len(ui.errors) == 1
    assert str(ui.errors[0]) == "API crash"


@pytest.mark.asyncio
async def test_agent_max_turns_limit() -> None:
    class MockClient(OllamaClient):
        async def chat(self, *_args: Any, **_kwargs: Any) -> Response:
            return _make_response(
                "looping",
                tool_calls=[{"function": {"name": "calculator", "arguments": {}}}],
            )

    agent = Agent(
        tools=[FakeTool()],
        client=MockClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT),
    )
    agent.max_turns = 3
    result = await agent.run("infinite loop")

    assert result.response == "looping"


class ReasoningMockClient(OllamaClient):
    """Mock client answering THINK, ACT and CHECK calls differently, recording each call."""

    def __init__(self, verdicts: list[str] | None = None) -> None:
        """Initialize the mock with the CHECK verdicts to return, in order."""
        super().__init__(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)
        self.verdicts = verdicts or []
        self.calls: list[tuple[str, list[dict[str, Any]]]] = []

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *_args: Any,
        **kwargs: Any,
    ) -> Response:
        if messages[-1]["content"].startswith(THINK_PREFIX):
            self.calls.append(("think", messages))
            if kwargs.get("on_chunk"):
                await kwargs["on_chunk"]("I should greet back.")
            return _make_response("I should greet back.")
        if kwargs.get("stream") is False:
            self.calls.append(("check", messages))
            return _make_response(self.verdicts.pop(0) if self.verdicts else "YES")
        self.calls.append(("act", messages))
        response = _make_response("Hello!")
        response.messages = [
            Message(role=m["role"], content=m["content"], response_time=0.0) for m in messages
        ]
        response.messages.append(Message(role="assistant", content="Hello!", response_time=0.0))
        return response


@pytest.mark.asyncio
async def test_agent_thinks_before_acting() -> None:
    client = ReasoningMockClient()
    ui = MockUIHandler()
    agent = Agent(client=client, ui_handler=ui)

    result = await agent.run("Hi")

    assert [kind for kind, _ in client.calls] == ["think", "act", "check"]
    assert ui.thinking == ["I should greet back.", "\n\n"]
    act_messages = client.calls[1][1]
    assert act_messages[-1]["role"] == "user"
    assert "I should greet back." in act_messages[-1]["content"]
    assert [(m.role, m.content) for m in result.messages] == [
        ("user", "Hi"),
        ("assistant", "Hello!"),
    ]


@pytest.mark.asyncio
async def test_agent_check_accepts_complete_answer() -> None:
    client = ReasoningMockClient(verdicts=["YES"])
    agent = Agent(client=client)

    result = await agent.run("Hi")

    assert [kind for kind, _ in client.calls] == ["think", "act", "check"]
    assert result.response == "Hello!"
    check_prompt = client.calls[2][1][0]["content"]
    assert "Hi" in check_prompt
    assert "Hello!" in check_prompt


@pytest.mark.asyncio
async def test_agent_check_retries_only_once() -> None:
    client = ReasoningMockClient(verdicts=["NO: missing the weather", "NO: still missing"])
    agent = Agent(client=client)

    result = await agent.run("Hi")

    assert [kind for kind, _ in client.calls] == ["think", "act", "check", "think", "act"]
    retry_messages = client.calls[4][1]
    assert any("missing the weather" in m["content"] for m in retry_messages)
    assert [(m.role, m.content) for m in result.messages] == [
        ("user", "Hi"),
        ("assistant", "Hello!"),
    ]


@pytest.mark.asyncio
async def test_agent_max_turns_forces_answer_without_tools() -> None:
    received_tools: list[list[dict[str, Any]] | None] = []

    class MockClient(OllamaClient):
        async def chat(
            self, messages: list[dict[str, Any]], *_args: Any, **kwargs: Any
        ) -> Response:
            if (reply := _reasoning_reply(messages, kwargs)) is not None:
                return reply
            received_tools.append(kwargs.get("tools"))
            return _make_response(
                "looping",
                tool_calls=[{"function": {"name": "calculator", "arguments": {}}}],
            )

    agent = Agent(
        tools=[FakeTool()],
        client=MockClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT),
    )
    agent.max_turns = 2
    await agent.run("infinite loop")

    assert len(received_tools) == 3
    assert received_tools[-1] == []


class TemperatureTool(FakeTool):
    """Fake tool with a multi-line description."""

    name = "get_temperature"

    def define(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "get_temperature",
                "description": "Get the current\ntemperature for a city.",
            },
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tools", "expected"),
    [
        ([], "Available tools:\n(none)"),
        (
            [FakeTool(), TemperatureTool()],
            (
                "Available tools:\n- calculator: \n"
                "- get_temperature: Get the current temperature for a city."
            ),
        ),
    ],
)
async def test_agent_think_prompt_lists_available_tools(tools: list[Any], expected: str) -> None:
    client = ReasoningMockClient(verdicts=["YES"])
    agent = Agent(tools=tools, client=client)

    await agent.run("Hi")

    think_prompt = client.calls[0][1][-1]["content"]
    assert think_prompt.endswith(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("thought", "expected_names"),
    [
        ("No tool needed.\nDECISION: ANSWER", []),
        ("Need the weather.\nDECISION: TOOL get_temperature", ["get_temperature"]),
        ("Need it.\ndecision: tool `calculator`", ["calculator"]),
        ("DECISION: TOOL calculator\nActually no.\nDECISION: ANSWER", []),
        ("Need it.\nDECISION: TOOL unknown_tool", ["calculator", "get_temperature"]),
        ("No decision line.", ["calculator", "get_temperature"]),
    ],
)
async def test_agent_act_tools_follow_think_decision(
    thought: str, expected_names: list[str]
) -> None:
    received_tools: list[list[dict[str, Any]]] = []

    class MockClient(OllamaClient):
        async def chat(
            self, messages: list[dict[str, Any]], *_args: Any, **kwargs: Any
        ) -> Response:
            if messages[-1]["content"].startswith(THINK_PREFIX):
                return _make_response(thought)
            if kwargs.get("stream") is False:
                return _make_response("YES")
            received_tools.append(kwargs.get("tools") or [])
            return _make_response("Done.")

    agent = Agent(
        tools=[FakeTool(), TemperatureTool()],
        client=MockClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT),
    )

    await agent.run("Hi")

    assert [t["function"]["name"] for t in received_tools[0]] == expected_names
