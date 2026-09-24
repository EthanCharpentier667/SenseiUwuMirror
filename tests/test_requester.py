"""Tests for the ``requester`` module."""

import json
import re
from typing import Any

import httpx
import pytest

from sensai import requester
from sensai.events import AsyncUIHandler


class MockUIHandler(AsyncUIHandler):
    def __init__(self, *, approval_response: bool = True) -> None:
        """Initialize MockUIHandler."""
        self.streamed: list[str] = []
        self.tool_calls: list[tuple[str, dict[str, Any]]] = []
        self.tool_results: list[tuple[str, Any]] = []
        self.errors: list[Exception] = []
        self.approval_response = approval_response

    async def on_stream_chunk(self, chunk: str) -> None:
        self.streamed.append(chunk)

    async def on_tool_call_request(self, name: str, arguments: dict[str, Any]) -> bool:
        self.tool_calls.append((name, arguments))
        return self.approval_response

    async def on_tool_call_result(self, name: str, result: Any) -> None:
        self.tool_results.append((name, result))

    async def on_error(self, error: Exception) -> None:
        self.errors.append(error)


@pytest.mark.asyncio
async def test_make_request_stream_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        async def aiter_lines(self):
            yield json.dumps({"message": {"content": "Hello"}})
            yield json.dumps({"message": {"content": " World"}})
            yield json.dumps({"done": True, "eval_count": 10})

    class MockStreamContext:
        async def __aenter__(self) -> MockResponse:
            return MockResponse()

        async def __aexit__(self, *args: object) -> None:
            pass

    class MockAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        def stream(self, *args: Any, **kwargs: Any) -> MockStreamContext:  # noqa: ARG002
            return MockStreamContext()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    ui_handler = MockUIHandler()
    res = await requester.make_request("url", {}, stream=True, ui_handler=ui_handler)

    assert res["response"] == "Hello World"
    assert res["eval_count"] == 10
    assert "".join(ui_handler.streamed) == "Hello World"


@pytest.mark.asyncio
async def test_get_sensei_response_tool_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTool:
        name = "get_weather"

        def define(self) -> dict[str, Any]:
            return {"type": "function", "function": {"name": "get_weather"}}

        def execute(self, **_kwargs: Any) -> str:
            return "Sunny"

    call_count = 0

    async def mock_make_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "response": "",
                "tool_calls": [{"function": {"name": "get_weather", "arguments": {}}}],
            }
        return {"response": "Final Answer", "tool_calls": []}

    monkeypatch.setattr(requester, "make_request", mock_make_request)
    monkeypatch.setenv("TOKEN", "test")

    ui_handler = MockUIHandler(approval_response=True)
    res = await requester.get_sensei_response(
        "Hello", tools=[FakeTool()], human_in_the_loop=True, ui_handler=ui_handler
    )

    assert res["response"] == "Final Answer"
    assert call_count == 2
    assert len(ui_handler.tool_calls) == 1
    assert ui_handler.tool_calls[0][0] == "get_weather"
    assert len(ui_handler.tool_results) == 1
    assert ui_handler.tool_results[0][0] == "get_weather"


@pytest.mark.asyncio
async def test_get_sensei_response_tool_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTool:
        name = "get_weather"

        def define(self) -> dict[str, Any]:
            return {"type": "function", "function": {"name": "get_weather"}}

        def execute(self, **_kwargs: Any) -> str:
            return "Sunny"

    call_count = 0

    async def mock_make_request(
        url: str, payload: dict[str, Any], *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "response": "",
                "tool_calls": [{"function": {"name": "get_weather", "arguments": {}}}],
            }
        messages = payload["messages"]
        assert messages[-1]["content"] == "Action cancelled by user."

        return {"response": "Understood.", "tool_calls": []}

    monkeypatch.setattr(requester, "make_request", mock_make_request)
    monkeypatch.setenv("TOKEN", "test")

    ui_handler = MockUIHandler(approval_response=False)
    res = await requester.get_sensei_response(
        "Hello", tools=[FakeTool()], human_in_the_loop=True, ui_handler=ui_handler
    )

    assert res["response"] == "Understood."
    assert call_count == 2
    assert len(ui_handler.tool_results) == 0


@pytest.mark.asyncio
async def test_get_sensei_response_unmatched_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = 0

    async def mock_make_request(
        url: str, payload: dict[str, Any], *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "response": "",
                "tool_calls": [{"function": {"name": "unknown_tool", "arguments": {}}}],
            }

        messages = payload["messages"]
        assert messages[-1]["content"] == "Tool 'unknown_tool' not found."
        return {"response": "Fixed.", "tool_calls": []}

    monkeypatch.setattr(requester, "make_request", mock_make_request)
    monkeypatch.setenv("TOKEN", "test")

    res = await requester.get_sensei_response("Hello", tools=[], human_in_the_loop=False)
    assert res["response"] == "Fixed."


@pytest.mark.asyncio
async def test_get_sensei_response_no_human_in_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTool:
        name = "get_weather"

        def define(self) -> dict[str, Any]:
            return {"type": "function", "function": {"name": "get_weather"}}

        def execute(self, **_kwargs: Any) -> str:
            return "Sunny"

    call_count = 0

    async def mock_make_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "response": "",
                "tool_calls": [{"function": {"name": "get_weather", "arguments": {}}}],
            }
        return {"response": "Done.", "tool_calls": []}

    monkeypatch.setattr(requester, "make_request", mock_make_request)
    monkeypatch.setenv("TOKEN", "test")

    ui_handler = MockUIHandler()
    await requester.get_sensei_response(
        "Hello", tools=[FakeTool()], human_in_the_loop=False, ui_handler=ui_handler
    )

    assert len(ui_handler.tool_calls) == 0
    assert len(ui_handler.tool_results) == 1


def test_get_buffered_response() -> None:
    requester.streaming_response_buffer.clear()
    requester.streaming_response_buffer.append("A")
    requester.streaming_response_buffer.append("B")
    assert requester.get_buffered_response() == "AB"
    assert requester.get_buffered_response() == ""


@pytest.mark.asyncio
async def test_make_request_non_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, str]:
            return {"result": "ok"}

    class MockAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def post(self, *args: Any, **kwargs: Any) -> MockResponse:  # noqa: ARG002
            return MockResponse()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    res = await requester.make_request("url", {}, stream=False)
    assert res == {"result": "ok"}


@pytest.mark.asyncio
async def test_make_request_stream_json_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        async def aiter_lines(self):
            yield "bad json"
            yield json.dumps({"done": True, "eval_count": 5})

    class MockStreamContext:
        async def __aenter__(self) -> MockResponse:
            return MockResponse()

        async def __aexit__(self, *args: object) -> None:
            pass

    class MockAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        def stream(self, *args: Any, **kwargs: Any) -> MockStreamContext:  # noqa: ARG002
            return MockStreamContext()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    res = await requester.make_request("url", {}, stream=True)
    assert res["eval_count"] == 5


@pytest.mark.asyncio
async def test_get_sensei_response_exception_propagation(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_make_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise ValueError("Network Error")

    monkeypatch.setattr(requester, "make_request", mock_make_request)
    monkeypatch.setenv("TOKEN", "test")
    ui_handler = MockUIHandler()
    with pytest.raises(ValueError, match="Network Error"):
        await requester.get_sensei_response("Hello", ui_handler=ui_handler)
    assert len(ui_handler.errors) == 1
    assert str(ui_handler.errors[0]) == "Network Error"


@pytest.mark.asyncio
async def test_get_sensei_response_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOKEN", raising=False)
    pattern = re.escape("API token not found in environment variables.")
    with pytest.raises(ValueError, match=pattern):
        await requester.get_sensei_response("Hello")


@pytest.mark.asyncio
async def test_get_sensei_response_no_messages_or_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKEN", "test")
    with pytest.raises(ValueError, match=re.escape("Either prompt or messages must be provided.")):
        await requester.get_sensei_response()
