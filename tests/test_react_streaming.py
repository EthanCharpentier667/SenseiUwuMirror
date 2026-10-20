"""Tests for the ``sensai.features.react.stream`` module and ReAct streaming."""

from typing import Any

import pytest

from sensai.agent import Agent
from sensai.client import OllamaClient, Response
from sensai.features.react.react import Decision, ReActController
from sensai.features.react.stream import StreamingThoughtExtractor
from sensai.ui.protocol import AsyncUIHandler

TEST_BASE_URL = "http://localhost:11434/api/chat"
TEST_TOKEN = "test-token"  # noqa: S105
TEST_TIMEOUT = 30.0


def _make_response(response: str = "") -> Response:
    return Response(
        response=response,
        respond_time=0.0,
        request_time=0.0,
        total_duration=0.0,
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


@pytest.mark.asyncio
async def test_extractor_json_thought_chunked() -> None:
    collected: list[str] = []

    async def on_chunk(text: str) -> None:
        collected.append(text)

    extractor = StreamingThoughtExtractor(on_chunk)
    chunks = [
        '{"tho',
        'ught": "Looking ',
        "up the information",
        ' now.", "missing": "nothing", "action": "final_answer", "args": {}}',
    ]
    for chunk in chunks:
        await extractor.feed(chunk)

    assert "".join(collected) == "Looking up the information now."
    assert extractor.has_emitted_thought is True


@pytest.mark.asyncio
async def test_extractor_escaped_characters() -> None:
    collected: list[str] = []

    async def on_chunk(text: str) -> None:
        collected.append(text)

    extractor = StreamingThoughtExtractor(on_chunk)
    chunks = [
        (
            '{"thought": "Line 1\\nLine 2 with \\"quotes\\", tab:\\t, backslash:\\\\, caf\\u00e9", '
            '"missing": "", "action": "final_answer", "args": {}}'
        )
    ]
    for chunk in chunks:
        await extractor.feed(chunk)

    expected = 'Line 1\nLine 2 with "quotes", tab:\t, backslash:\\, café'
    assert "".join(collected) == expected


@pytest.mark.asyncio
async def test_extractor_think_tags() -> None:
    collected: list[str] = []

    async def on_chunk(text: str) -> None:
        collected.append(text)

    extractor = StreamingThoughtExtractor(on_chunk)
    chunks = [
        "<th",
        "ink>First stage of reasoning.",
        "</th",
        (
            'ink>{"thought": "Second thought", "missing": "none", '
            '"action": "final_answer", "args": {}}'
        ),
    ]
    for chunk in chunks:
        await extractor.feed(chunk)

    assert "".join(collected) == "First stage of reasoning.Second thought"


@pytest.mark.asyncio
async def test_extractor_ignores_after_done() -> None:
    collected: list[str] = []

    async def on_chunk(text: str) -> None:
        collected.append(text)

    extractor = StreamingThoughtExtractor(on_chunk)
    await extractor.feed('{"thought": "done", "missing": "something", "action": "test"}')
    await extractor.feed('{"thought": "should be ignored"}')

    assert "".join(collected) == "done"


@pytest.mark.asyncio
async def test_extractor_none_callback() -> None:
    extractor = StreamingThoughtExtractor(None)
    await extractor.feed('{"thought": "silently parsed", "missing": ""}')
    assert extractor.has_emitted_thought is True


class StreamingPlanClient(OllamaClient):
    """Mock client streaming planning chunks."""

    def __init__(self, stream_chunks: list[str], full_json: str) -> None:
        """Initialize mock client."""
        super().__init__(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)
        self.stream_chunks = stream_chunks
        self.full_json = full_json

    async def chat(
        self,
        messages: list[dict[str, Any]],  # noqa: ARG002
        *_args: Any,
        **kwargs: Any,
    ) -> Response:
        on_chunk = kwargs.get("on_chunk")
        if on_chunk:
            for chunk in self.stream_chunks:
                await on_chunk(chunk)
        return _make_response(self.full_json)


class CapturingUIHandler(AsyncUIHandler):
    """UI handler capturing thinking chunks."""

    def __init__(self) -> None:
        """Initialize capturing handler."""
        self.thinking: list[str] = []
        self.spinners: list[str] = []

    async def on_stream_chunk(self, _chunk: str) -> None:
        pass

    async def on_stream_end(self) -> None:
        pass

    async def start_spinner(self, message: str) -> None:
        self.spinners.append(message)

    async def stop_spinner(self) -> None:
        pass

    async def on_thinking_chunk(self, chunk: str) -> None:
        self.thinking.append(chunk)

    async def on_tool_call_request(self, _name: str, _arguments: dict[str, Any]) -> bool:
        return True

    async def on_tool_call_result(
        self, _name: str, _result: Any, *, show_output: bool = False
    ) -> None:
        pass

    async def render_output(self, _content: Any, *, title: str = "Output") -> None:
        pass

    async def on_error(self, _error: Exception | str, *, title: str = "Error") -> None:
        pass

    async def on_system_message(self, _message: Any) -> None:
        pass

    async def prompt_choice(
        self, _title: str, _text: str, _choices: list[tuple[str, str]]
    ) -> str | None:
        return None

    async def prompt_input(self, _title: str, _text: str) -> str | None:
        return None


@pytest.mark.asyncio
async def test_agent_plan_streams_thought_and_action() -> None:
    chunks = [
        '{"tho',
        'ught": "Need ',
        'weather info", ',
        '"action": "final_answer", "args": {}}',
    ]
    full_json = '{"thought": "Need weather info", "action": "final_answer", "args": {}}'
    client = StreamingPlanClient(chunks, full_json)
    ui = CapturingUIHandler()
    agent = Agent(client=client, ui_handler=ui)

    controller = ReActController([])
    decision = await agent._plan([{"role": "user", "content": "Weather?"}], controller)  # noqa: SLF001

    assert decision == Decision(
        thought="Need weather info",
        action="final_answer",
        args={},
    )
    thought_output = "".join(ui.thinking)
    assert "Need weather info" in thought_output
    assert "→ final_answer\n" in thought_output
