"""Tests for the ``sensai.agent`` module."""

import json
import re
from typing import Any

import pytest

from sensai.agent import Agent
from sensai.client import OllamaClient, Response
from sensai.data.session.message import Message
from sensai.features.features import MCP, REACT, TOOLS, Features
from sensai.features.react.react import FINAL_ANSWER
from sensai.features.tools.mcp.mcp_tools import MCPTools
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


def _step(action: str, args: dict[str, Any] | None = None, thought: str = "thinking") -> str:
    return json.dumps({"thought": thought, "action": action, "args": args or {}})


class ScriptedClient(OllamaClient):
    """Mock client replaying planning steps in order, then answering with ``answer``.

    Planning calls are told apart by their ``response_format``; once the script is used
    up, every planning call picks the final answer.
    """

    def __init__(
        self, steps: list[str] | None = None, answer: str = "Hello!", *, vision: bool = False
    ) -> None:
        """Initialize the mock with the planning replies, the final answer and capabilities."""
        super().__init__(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)
        self.steps = list(steps or [])
        self.answer = answer
        self.vision = vision
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

    async def capabilities(self, model: str) -> set[str]:  # noqa: ARG002
        return {"completion", "vision"} if self.vision else {"completion"}


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

    async def on_stream_end(self) -> None:
        pass

    async def start_spinner(self, message: str) -> None:
        pass

    async def stop_spinner(self) -> None:
        pass

    async def on_tool_call_request(self, name: str, arguments: dict[str, Any]) -> bool:
        self.tool_requests.append((name, arguments))
        return self.approval

    async def on_tool_call_result(
        self,
        name: str,
        result: Any,
        *,
        show_output: bool = False,  # noqa: ARG002
    ) -> None:
        self.tool_results.append((name, result))

    async def render_output(self, content: Any, *, title: str = "Output") -> None:
        pass

    async def on_error(
        self,
        error: Exception | str,
        *,
        title: str = "Error",  # noqa: ARG002
    ) -> None:
        self.errors.append(error if isinstance(error, Exception) else Exception(error))

    async def on_thinking_chunk(self, chunk: str) -> None:
        self.thinking.append(chunk)

    async def on_system_message(self, message: Any) -> None:
        pass

    async def prompt_choice(
        self, _title: str, _text: str, choices: list[tuple[str, str]]
    ) -> str | None:
        return choices[0][0] if choices else None

    async def prompt_input(self, _title: str, _text: str) -> str | None:
        return "mock_input"


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


class ImageTool(FakeTool):
    """Fake tool returning an image, like the screenshot tool."""

    name = "screenshot"
    requires = frozenset({"vision"})

    def define(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": "screenshot"}}

    def execute(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]  # noqa: ARG002
        return {"message": "Screenshot saved.", "images": ["aW1n"]}


class DocumentTool(FakeTool):
    """Fake tool returning a document to ingest, like the file read tool."""

    name = "file_read"

    def define(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": "file_read"}}

    def execute(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]  # noqa: ARG002
        return {"content": "notes", "document": "notes.md"}


class BrokenTool(FakeTool):
    """Fake tool that always raises."""

    name = "broken"

    def define(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": "broken"}}

    def execute(self, **kwargs: Any) -> str:  # noqa: ARG002
        raise RuntimeError("Tool execution failed unexpectedly")


def _instructions(call: dict[str, Any]) -> str:
    return str(next(m["content"] for m in call["messages"] if m.get("ephemeral")))


def _trajectory(call: dict[str, Any]) -> str:
    return "\n".join(m["content"] for m in call["messages"] if m["role"] in {"assistant", "tool"})


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
    assert client.plans == []
    assert len(client.answers) == 1
    assert client.answers[0]["tools"] == []
    assert ui.thinking == []
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

    fused = "Different system prompt\n\nCustom system prompt."
    assert len(client.answers[0]["messages"]) == 2
    assert client.answers[0]["messages"][0]["content"] == fused


@pytest.mark.asyncio
async def test_agent_plan_is_constrained_and_never_sent_as_user() -> None:
    client = ScriptedClient()
    agent = Agent(tools=[FakeTool()], client=client)

    await agent.run("Hi")

    plan = client.plans[0]
    assert plan["tools"] == []
    assert plan["options"] == {"temperature": 0}
    assert plan["response_format"]["properties"]["action"]["enum"] == ["calculator", FINAL_ANSWER]
    assert plan["messages"][-1] == {"role": "user", "content": "Hi"}
    assert plan["messages"][-2]["role"] == "system"
    assert [m for m in plan["messages"] if m["role"] == "user"] == [
        {"role": "user", "content": "Hi"}
    ]


@pytest.mark.asyncio
async def test_agent_runs_tool_then_answers_with_its_result() -> None:
    client = ScriptedClient(steps=[_step("calculator", {"expr": "2+2"})], answer="The answer is 4.")
    ui = MockUIHandler(approval=True)
    agent = Agent(
        tools=[FakeTool()],
        trust_level="none",
        ui_handler=ui,
        client=client,
    )

    result = await agent.run("What is 2+2?")

    assert result.response == "The answer is 4."
    assert ui.tool_requests == [("calculator", {"expr": "2+2"})]
    assert ui.tool_results == [("calculator", "result: 2+2")]
    assert len(client.plans) == 2
    assert client.plans[1]["messages"][-2:] == [
        {
            "role": "assistant",
            "content": '{"thought": "thinking", "action": "calculator", "args": {"expr": "2+2"}}',
            "ephemeral": True,
        },
        {
            "role": "tool",
            "tool_name": "calculator",
            "content": "Observation: result: 2+2",
            "ephemeral": True,
        },
    ]
    assert "result: 2+2" in _system_texts(client.answers[0])
    assert [(m.role, m.content) for m in result.messages] == [
        ("user", "What is 2+2?"),
        ("assistant", "The answer is 4."),
    ]


@pytest.mark.asyncio
async def test_agent_async_tool_execution() -> None:
    client = ScriptedClient(
        steps=[_step("async_calculator", {"expr": "3+3"})], answer="The answer is 6."
    )
    ui = MockUIHandler(approval=True)
    agent = Agent(
        tools=[AsyncFakeTool()],
        trust_level="none",
        ui_handler=ui,
        client=client,
    )

    result = await agent.run("What is 3+3?")

    assert result.response == "The answer is 6."
    assert ui.tool_results == [("async_calculator", "async result: 3+3")]


@pytest.mark.asyncio
async def test_agent_tool_denied_by_user() -> None:
    client = ScriptedClient(steps=[_step("calculator", {"expr": "2+2"})])
    ui = MockUIHandler(approval=False)
    agent = Agent(
        tools=[FakeTool()],
        trust_level="none",
        ui_handler=ui,
        client=client,
    )

    await agent.run("What is 2+2?")

    assert ui.tool_results == []
    assert "Observation (refused): Action cancelled by user." in _trajectory(client.plans[1])
    assert len(client.answers[0]["messages"]) == 1


@pytest.mark.asyncio
async def test_agent_rejects_invalid_step_without_running_it() -> None:
    client = ScriptedClient(steps=[_step("unknown"), _step("calculator", {})])
    ui = MockUIHandler()
    agent = Agent(tools=[FakeTool()], trust_level="none", ui_handler=ui, client=client)

    await agent.run("Hi")

    assert ui.tool_requests == []
    planning = _trajectory(client.plans[2])
    assert "'unknown' is not available now" in planning
    assert "missing argument(s): expr" in planning


@pytest.mark.asyncio
async def test_agent_stops_when_the_model_repeats_a_call() -> None:
    call = _step("calculator", {"expr": "2+2"})
    client = ScriptedClient(steps=[call, call, call])
    ui = MockUIHandler()
    agent = Agent(tools=[FakeTool()], ui_handler=ui, client=client)

    await agent.run("What is 2+2?")

    assert ui.tool_results == [("calculator", "result: 2+2")]
    assert len(client.plans) == 2
    assert len(client.answers) == 1


@pytest.mark.asyncio
async def test_agent_tool_error_becomes_observation() -> None:
    client = ScriptedClient(steps=[_step("broken")], answer="Sorry.")
    ui = MockUIHandler()
    agent = Agent(tools=[BrokenTool()], ui_handler=ui, client=client)

    result = await agent.run("hello")

    assert result.response == "Sorry."
    assert [str(e) for e in ui.errors] == ["Tool execution failed unexpectedly"]
    assert "Error: Tool execution failed unexpectedly" in _trajectory(client.plans[1])


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
async def test_agent_keeps_acting_until_the_model_chooses_the_final_answer() -> None:
    client = ScriptedClient(
        steps=[
            _step("calculator", {"expr": "2+2"}, thought="Compute it."),
            _step("async_calculator", {"expr": "2*2"}, thought="Check it another way."),
        ],
        answer="4.",
    )
    ui = MockUIHandler()
    agent = Agent(tools=[FakeTool(), AsyncFakeTool()], ui_handler=ui, client=client)

    await agent.run("What is 2+2?")

    assert ui.tool_results == [
        ("calculator", "result: 2+2"),
        ("async_calculator", "async result: 2*2"),
    ]
    assert len(client.plans) == 3
    trajectory = _trajectory(client.plans[2])
    assert '{"thought": "Compute it.", "action": "calculator"' in trajectory
    assert "Observation: async result: 2*2" in trajectory
    assert ui.thinking[0] == 'Compute it.\n→ calculator {"expr": "2+2"}\n\n'


@pytest.mark.asyncio
async def test_agent_stops_planning_once_no_tool_can_run() -> None:
    client = ScriptedClient(steps=[_step("calculator", {"expr": str(n)}) for n in range(5)])
    ui = MockUIHandler()
    agent = Agent(tools=[FakeTool()], ui_handler=ui, client=client)

    await agent.run("loop")

    assert len(ui.tool_results) == 2
    assert len(client.plans) == 2
    assert len(client.answers) == 1


@pytest.mark.asyncio
async def test_agent_shows_tool_images_to_a_vision_model_only_for_this_run() -> None:
    client = ScriptedClient(steps=[_step("screenshot")], answer="A terminal.", vision=True)
    ui = MockUIHandler()
    agent = Agent(tools=[ImageTool()], trust_level="total", ui_handler=ui, client=client)

    result = await agent.run("What is on my screen?")

    assert ui.tool_results == [("screenshot", {"message": "Screenshot saved."})]
    assert "images" not in client.plans[0]["messages"][-1]
    assert client.plans[1]["messages"][-1]["role"] == "tool"
    for call, user in [(client.plans[1], -3), (client.answers[0], -1)]:
        assert call["messages"][user] == {
            "role": "user",
            "content": "What is on my screen?",
            "images": ["aW1n"],
        }
        assert "aW1n" not in _instructions(call)
    assert "1 image(s) from this tool are attached" in _instructions(client.answers[0])
    assert [(m.role, m.content) for m in result.messages] == [
        ("user", "What is on my screen?"),
        ("assistant", "A terminal."),
    ]


@pytest.mark.asyncio
async def test_agent_keeps_the_documents_tools_read_for_this_run_only() -> None:
    client = ScriptedClient(steps=[_step("file_read")], answer="Notes.")
    ui = MockUIHandler()
    agent = Agent(tools=[DocumentTool()], trust_level="total", ui_handler=ui, client=client)

    await agent.run("Read my notes.")

    assert agent.read_documents == ["notes.md"]
    assert ui.tool_results == [("file_read", {"content": "notes"})]
    assert "notes.md" not in _trajectory(client.plans[1])

    await agent.run("Hello.")

    assert agent.read_documents == []


@pytest.mark.asyncio
async def test_agent_hides_tools_needing_a_capability_the_model_lacks() -> None:
    client = ScriptedClient(steps=[_step("screenshot")], vision=False)
    agent = Agent(tools=[FakeTool(), ImageTool()], trust_level="total", client=client)

    await agent.run("What is on my screen?")

    assert client.plans[0]["response_format"]["properties"]["action"]["enum"] == [
        "calculator",
        FINAL_ANSWER,
    ]


@pytest.mark.asyncio
async def test_agent_never_sends_images_to_a_model_without_vision() -> None:
    class UndeclaredImageTool(ImageTool):
        requires = frozenset()

    client = ScriptedClient(steps=[_step("screenshot")], vision=False)
    agent = Agent(tools=[UndeclaredImageTool()], trust_level="total", client=client)

    await agent.run("What is on my screen?")

    assert len(client.plans) == 2
    for call in [*client.plans, *client.answers]:
        assert all("images" not in message for message in call["messages"])


@pytest.mark.asyncio
async def test_agent_drops_undeclared_arguments() -> None:
    client = ScriptedClient(steps=[_step("calculator", {"expr": "2+2", "thought": "copied"})])
    ui = MockUIHandler()
    agent = Agent(tools=[FakeTool()], trust_level="none", ui_handler=ui, client=client)

    await agent.run("What is 2+2?")

    assert ui.tool_requests == [("calculator", {"expr": "2+2"})]


@pytest.mark.asyncio
async def test_agent_instructions_never_come_last() -> None:
    client = ScriptedClient(steps=[_step("calculator", {"expr": "2+2"})])
    agent = Agent(tools=[FakeTool()], trust_level="total", client=client)
    agent.system_prompt = "Be nice."

    await agent.run("What is 2+2?")

    user = {"role": "user", "content": "What is 2+2?"}
    assert client.plans[0]["messages"][-1] == user
    assert client.plans[1]["messages"][-3] == user
    assert client.plans[1]["messages"][-1]["role"] == "tool"
    assert client.answers[0]["messages"][-1] == user
    assert client.answers[0]["messages"][1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_agent_skips_the_react_loop_when_react_is_disabled() -> None:
    client = ScriptedClient(steps=[_step("calculator", {"a": 1, "b": 2})])
    agent = Agent(tools=[FakeTool()], client=client, features=Features.from_disabled([REACT]))

    result = await agent.run("What is 1 + 2?")

    assert result.response == "Hello!"
    assert client.plans == []
    assert len(client.answers) == 1


@pytest.mark.asyncio
async def test_agent_uses_no_tool_when_tools_are_disabled() -> None:
    client = ScriptedClient()
    agent = Agent(tools=[FakeTool()], client=client, features=Features.from_disabled([TOOLS]))

    await agent.run("Hi")

    assert agent.available_tools() == []
    assert client.plans == []


def test_agent_hides_mcp_tools_when_mcp_is_disabled() -> None:
    mcp_tool = MCPTools.__new__(MCPTools)
    mcp_tool.name = "remote"
    local_tool = FakeTool()
    features = Features()
    agent = Agent(tools=[local_tool, mcp_tool], client=ScriptedClient(), features=features)

    assert agent.available_tools() == [local_tool, mcp_tool]
    features.set(MCP, enabled=False)
    assert agent.available_tools() == [local_tool]


def test_agent_hides_a_single_disabled_tool() -> None:
    tool = FakeTool()
    features = Features.from_disabled([], tools=[tool.name])
    agent = Agent(tools=[tool], client=ScriptedClient(), features=features)

    assert agent.available_tools() == []
    features.set_tool(tool.name, enabled=True)
    assert agent.available_tools() == [tool]


class NoSchemaClient(ScriptedClient):
    """Mock client of a server answering nothing to a schema, like Ollama Cloud.

    Its planning calls are the non-streamed ones; those sent with a schema get an empty reply.
    """

    async def chat(self, messages: list[dict[str, Any]], *_args: Any, **kwargs: Any) -> Response:
        if kwargs.get("stream", True):
            return await super().chat(messages, **kwargs)
        self.plans.append({"messages": messages, **kwargs})
        if kwargs.get("response_format") is not None:
            return _make_response("")
        return _make_response(self.steps.pop(0) if self.steps else _step(FINAL_ANSWER))


@pytest.mark.asyncio
async def test_agent_plans_without_the_schema_once_the_server_ignores_it() -> None:
    client = NoSchemaClient(steps=[_step("calculator", {"expr": "2+2"})], answer="4.")
    agent = Agent(tools=[FakeTool()], trust_level="total", client=client)

    result = await agent.run("What is 2+2?")

    assert result.response == "4."
    assert [call.get("response_format") is not None for call in client.plans] == [
        True,
        False,
        False,
    ]
    assert '"action": "<one of: calculator, final_answer>"' in _instructions(client.plans[1])
    assert "result: 2+2" in _system_texts(client.answers[0])
