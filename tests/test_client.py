"""Tests for the ``sensai.client`` module."""

import json
import re
from typing import Any

import httpx
import pytest

from sensai.client import OllamaClient
from sensai.ui.protocol import AsyncUIHandler


class MockUIHandler(AsyncUIHandler):
    """Mock UI Handler for testing."""

    def __init__(self) -> None:
        """Initialize MockUIHandler."""
        self.streamed: list[str] = []
        self.errors: list[Exception] = []

    async def on_stream_chunk(self, chunk: str) -> None:
        self.streamed.append(chunk)

    async def on_tool_call_request(self, _name: str, _arguments: dict[str, Any]) -> bool:
        return True

    async def on_tool_call_result(self, name: str, result: Any) -> None:
        pass

    async def on_error(self, error: Exception) -> None:
        self.errors.append(error)


@pytest.mark.asyncio
async def test_client_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOKEN", raising=False)
    client = OllamaClient(token=None)
    pattern = re.escape("API token not found in environment variables.")
    with pytest.raises(ValueError, match=pattern):
        await client.chat(messages=[{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_client_chat_non_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, Any]:
            return {"response": "Hello non-stream"}

    class MockAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def post(self, *_args: Any, **_kwargs: Any) -> MockResponse:
            return MockResponse()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    monkeypatch.setenv("TOKEN", "test_env_token")
    client = OllamaClient()
    result = await client.chat(
        messages=[{"role": "user", "content": "hi"}],
        stream=False,
    )
    assert result == {"response": "Hello non-stream"}


@pytest.mark.asyncio
async def test_client_chat_stream_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        async def aiter_lines(self):
            yield json.dumps({"message": {"content": "Hello"}})
            yield json.dumps({"message": {"content": " world!"}})
            yield json.dumps(
                {
                    "done": True,
                    "done_reason": "stop",
                    "eval_count": 5,
                    "prompt_eval_count": 3,
                    "total_duration": 100,
                }
            )

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

        def stream(self, *_args: Any, **_kwargs: Any) -> MockStreamContext:
            return MockStreamContext()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    monkeypatch.setenv("TOKEN", "test_env_token")
    ui_handler = MockUIHandler()
    client = OllamaClient()
    res = await client.chat(
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
        ui_handler=ui_handler,
    )

    assert res["response"] == "Hello world!"
    assert res["token_used"] == 8
    assert res["stop_reason"] == "stop"
    assert "".join(ui_handler.streamed) == "Hello world!"


@pytest.mark.asyncio
async def test_client_chat_stream_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        async def aiter_lines(self):
            yield "invalid json line"
            yield json.dumps(
                {
                    "message": {
                        "content": "ok",
                        "tool_calls": [{"function": {"name": "f", "arguments": {}}}],
                    },
                    "done": True,
                }
            )

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

        def stream(self, *_args: Any, **_kwargs: Any) -> MockStreamContext:
            return MockStreamContext()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    monkeypatch.setenv("TOKEN", "test_env_token")
    client = OllamaClient()
    res = await client.chat(
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
    )
    assert res["response"] == "ok"
    assert len(res["tool_calls"]) == 1
