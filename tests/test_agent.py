"""Tests for the ``sensai.agent`` module."""

import re
from typing import Any

import pytest

from sensai.agent import Agent
from sensai.client import OllamaClient
from sensai.ui.protocol import AsyncUIHandler


class MockUIHandler(AsyncUIHandler):
    """Mock UI Handler for testing Agent."""

    def __init__(self, *, approval: bool = True) -> None:
        """Initialize the mock UI handler."""
        self.streamed: list[str] = []
        self.tool_requests: list[tuple[str, dict[str, Any]]] = []
        self.tool_results: list[tuple[str, Any]] = []
        self.errors: list[Exception] = []
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
    agent = Agent()
    pattern = re.escape("Either prompt or messages must be provided.")
    with pytest.raises(ValueError, match=pattern):
        await agent.run()


@pytest.mark.asyncio
async def test_agent_system_prompt_injection() -> None:
    captured: dict[str, Any] = {}

    class MockClient(OllamaClient):
        async def chat(
            self,
            messages: list[dict[str, Any]],
            *_args: Any,
            **_kwargs: Any,
        ) -> dict[str, Any]:
            captured["messages"] = messages
            return {"response": "ok", "tool_calls": []}

    agent = Agent(client=MockClient())
    agent.system_prompt = "You are a helpful assistant."
    await agent.run("Hello")

    assert captured["messages"] == [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
    ]


@pytest.mark.asyncio
async def test_agent_system_prompt_not_duplicated() -> None:
    captured: dict[str, Any] = {}

    class MockClient(OllamaClient):
        async def chat(
            self,
            messages: list[dict[str, Any]],
            *_args: Any,
            **_kwargs: Any,
        ) -> dict[str, Any]:
            captured["messages"] = messages
            return {"response": "ok", "tool_calls": []}

    agent = Agent(client=MockClient())
    existing = [
        {"role": "system", "content": "Custom system prompt."},
        {"role": "user", "content": "Hi"},
    ]
    await agent.run(messages=existing, system_prompt="Different system prompt")

    assert len(captured["messages"]) == 2
    assert captured["messages"][0]["content"] == "Custom system prompt."


@pytest.mark.asyncio
async def test_agent_tool_loop_and_execution() -> None:
    turns = 0

    class MockClient(OllamaClient):
        async def chat(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            nonlocal turns
            turns += 1
            if turns == 1:
                return {
                    "response": "",
                    "tool_calls": [
                        {"function": {"name": "calculator", "arguments": {"expr": "2+2"}}}
                    ],
                }
            return {"response": "The answer is 4.", "tool_calls": []}

    ui = MockUIHandler(approval=True)
    tool = FakeTool()
    agent = Agent(tools=[tool], human_in_the_loop=True, ui_handler=ui, client=MockClient())

    result = await agent.run("What is 2+2?")

    assert result["response"] == "The answer is 4."
    assert turns == 2
    assert len(ui.tool_requests) == 1
    assert ui.tool_requests[0] == ("calculator", {"expr": "2+2"})
    assert len(ui.tool_results) == 1
    assert ui.tool_results[0] == ("calculator", "result: 2+2")


@pytest.mark.asyncio
async def test_agent_async_tool_execution() -> None:
    turns = 0

    class MockClient(OllamaClient):
        async def chat(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            nonlocal turns
            turns += 1
            if turns == 1:
                return {
                    "response": "",
                    "tool_calls": [
                        {"function": {"name": "async_calculator", "arguments": {"expr": "3+3"}}}
                    ],
                }
            return {"response": "The answer is 6.", "tool_calls": []}

    ui = MockUIHandler(approval=True)
    tool = AsyncFakeTool()
    agent = Agent(tools=[tool], human_in_the_loop=False, ui_handler=ui, client=MockClient())

    result = await agent.run("What is 3+3?")

    assert result["response"] == "The answer is 6."
    assert len(ui.tool_results) == 1
    assert ui.tool_results[0] == ("async_calculator", "async result: 3+3")


@pytest.mark.asyncio
async def test_agent_tool_denied_by_user() -> None:
    turns = 0
    captured_messages: list[dict[str, Any]] = []

    class MockClient(OllamaClient):
        async def chat(
            self,
            messages: list[dict[str, Any]],
            *_args: Any,
            **_kwargs: Any,
        ) -> dict[str, Any]:
            nonlocal turns
            turns += 1
            if turns == 1:
                return {
                    "response": "",
                    "tool_calls": [
                        {"function": {"name": "calculator", "arguments": {"expr": "2+2"}}}
                    ],
                }
            captured_messages.extend(messages)
            return {"response": "Operation cancelled.", "tool_calls": []}

    ui = MockUIHandler(approval=False)
    tool = FakeTool()
    agent = Agent(tools=[tool], human_in_the_loop=True, ui_handler=ui, client=MockClient())

    result = await agent.run("What is 2+2?")

    assert result["response"] == "Operation cancelled."
    assert len(ui.tool_results) == 0
    assert captured_messages[-1] == {
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
            self,
            messages: list[dict[str, Any]],
            *_args: Any,
            **_kwargs: Any,
        ) -> dict[str, Any]:
            nonlocal turns
            turns += 1
            if turns == 1:
                return {
                    "response": "",
                    "tool_calls": [{"function": {"name": "unknown", "arguments": {}}}],
                }
            captured_messages.extend(messages)
            return {"response": "Fixed.", "tool_calls": []}

    agent = Agent(tools=[], client=MockClient())
    result = await agent.run("Run unknown tool")

    assert result["response"] == "Fixed."
    assert captured_messages[-1] == {
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
        async def chat(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {
                "response": "",
                "tool_calls": [{"function": {"name": "broken", "arguments": {}}}],
            }

    ui = MockUIHandler()
    agent = Agent(tools=[BrokenTool()], ui_handler=ui, client=MockClient())

    with pytest.raises(RuntimeError, match="Tool execution failed unexpectedly"):
        await agent.run("hello")

    assert len(ui.errors) == 1
    assert str(ui.errors[0]) == "Tool execution failed unexpectedly"


@pytest.mark.asyncio
async def test_agent_error_notifies_ui() -> None:
    class MockClient(OllamaClient):
        async def chat(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("API crash")

    ui = MockUIHandler()
    agent = Agent(ui_handler=ui, client=MockClient())

    with pytest.raises(RuntimeError, match="API crash"):
        await agent.run("hello")

    assert len(ui.errors) == 1
    assert str(ui.errors[0]) == "API crash"


@pytest.mark.asyncio
async def test_agent_max_turns_limit() -> None:
    class MockClient(OllamaClient):
        async def chat(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {
                "response": "looping",
                "tool_calls": [{"function": {"name": "calculator", "arguments": {}}}],
            }

    agent = Agent(tools=[FakeTool()], client=MockClient())
    agent.max_turns = 3
    result = await agent.run("infinite loop")

    assert result["response"] == "looping"
