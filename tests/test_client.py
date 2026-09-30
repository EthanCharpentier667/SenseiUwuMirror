"""Tests for the ``sensai.client`` module."""

import json
import re
from typing import Any

import httpx
import pytest

from sensai.client import OllamaClient
from sensai.ui.protocol import AsyncUIHandler

TEST_BASE_URL = "http://localhost:11434/api/chat"
TEST_TIMEOUT = 30.0


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

    async def on_thinking_chunk(self, chunk: str) -> None:
        pass

    async def on_system_message(self, message: Any) -> None:
        pass


@pytest.mark.asyncio
async def test_client_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOKEN", raising=False)
    client = OllamaClient(base_url=TEST_BASE_URL, token=None, timeout=TEST_TIMEOUT)
    pattern = re.escape("API token not found in environment variables.")
    with pytest.raises(ValueError, match=pattern):
        await client.chat(messages=[{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_client_chat_non_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, Any]:
            return {
                "message": {
                    "content": "Hello non-stream",
                    "tool_calls": [{"function": {"name": "test_tool", "arguments": {}}}],
                },
                "done_reason": "stop",
                "eval_count": 5,
                "prompt_eval_count": 3,
                "total_duration": 42,
            }

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
    client = OllamaClient(base_url=TEST_BASE_URL, token=None, timeout=TEST_TIMEOUT)
    result = await client.chat(
        messages=[{"role": "user", "content": "hi"}],
        stream=False,
    )
    assert result.response == "Hello non-stream"
    assert result.tool_calls == [{"function": {"name": "test_tool", "arguments": {}}}]
    assert result.token_used == 8
    assert result.stop_reason == "stop"


@pytest.mark.asyncio
async def test_client_chat_non_stream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, Any]:
            return {"error": "model not found"}

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
    client = OllamaClient(base_url=TEST_BASE_URL, token=None, timeout=TEST_TIMEOUT)
    with pytest.raises(RuntimeError, match="Ollama error: model not found"):
        await client.chat(messages=[{"role": "user", "content": "hi"}], stream=False)


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
    client = OllamaClient(base_url=TEST_BASE_URL, token=None, timeout=TEST_TIMEOUT)
    res = await client.chat(
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
        ui_handler=ui_handler,
    )

    assert res.response == "Hello world!"
    assert res.token_used == 8
    assert res.stop_reason == "stop"
    assert "".join(ui_handler.streamed) == "Hello world!"


@pytest.mark.asyncio
async def test_client_chat_stream_error_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        async def aiter_lines(self):
            yield json.dumps({"error": "something went wrong in stream"})

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
    client = OllamaClient(base_url=TEST_BASE_URL, token=None, timeout=TEST_TIMEOUT)
    with pytest.raises(RuntimeError, match="Ollama error: something went wrong in stream"):
        await client.chat(messages=[{"role": "user", "content": "hi"}], stream=True)


@pytest.mark.asyncio
async def test_client_chat_stream_incomplete_without_done(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        async def aiter_lines(self):
            yield json.dumps({"message": {"content": "incomplete..."}})

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
    client = OllamaClient(base_url=TEST_BASE_URL, token=None, timeout=TEST_TIMEOUT)
    pattern = re.escape("Incomplete response: stream ended without done event.")
    with pytest.raises(RuntimeError, match=pattern):
        await client.chat(messages=[{"role": "user", "content": "hi"}], stream=True)


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
    client = OllamaClient(base_url=TEST_BASE_URL, token=None, timeout=TEST_TIMEOUT)
    res = await client.chat(
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
    )
    assert res.response == "ok"
    assert len(res.tool_calls) == 1


class MockEmbedResponse:
    """Mock response of Ollama's embed endpoint."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize MockEmbedResponse with the JSON body to return."""
        self.data = data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        return self.data


def _mock_embed_endpoint(
    monkeypatch: pytest.MonkeyPatch, data: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Replace httpx.AsyncClient with one answering every POST with ``data``.

    If ``data`` is None, it answers with one fake embedding per input instead.
    Returns the list the sent requests (url and json) get appended to.
    """
    sent: list[dict[str, Any]] = []

    class MockAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def post(self, url: httpx.URL, **kwargs: Any) -> MockEmbedResponse:
            sent.append({"url": str(url), "json": kwargs["json"]})
            if data is not None:
                return MockEmbedResponse(data)
            inputs = kwargs["json"]["input"]
            return MockEmbedResponse({"embeddings": [[float(i)] for i in range(len(inputs))]})

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    monkeypatch.setenv("TOKEN", "test_env_token")
    return sent


@pytest.mark.asyncio
async def test_client_embed_posts_inputs_to_embed_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = _mock_embed_endpoint(monkeypatch)
    client = OllamaClient(base_url=TEST_BASE_URL, token=None, timeout=TEST_TIMEOUT)

    embeddings = await client.embed(["a", "b"], "nomic-embed-text")

    assert embeddings == [[0.0], [1.0]]
    assert sent == [
        {
            "url": "http://localhost:11434/api/embed",
            "json": {"model": "nomic-embed-text", "input": ["a", "b"]},
        }
    ]


@pytest.mark.asyncio
async def test_client_embed_raises_on_ollama_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_embed_endpoint(monkeypatch, {"error": "model not found"})
    client = OllamaClient(base_url=TEST_BASE_URL, token=None, timeout=TEST_TIMEOUT)

    with pytest.raises(RuntimeError, match="model not found"):
        await client.embed(["hello"], "missing")
