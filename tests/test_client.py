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

    async def on_stream_end(self) -> None:
        pass

    async def start_spinner(self, message: str) -> None:
        pass

    async def stop_spinner(self) -> None:
        pass

    async def on_tool_call_request(self, _name: str, _arguments: dict[str, Any]) -> bool:
        return True

    async def on_tool_call_result(
        self, name: str, result: Any, *, show_output: bool = False
    ) -> None:
        pass

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
        pass

    async def on_prompt(self, payload: dict[str, Any]) -> None:
        pass

    async def on_context_warning(self, used: int, limit: int) -> None:
        pass

    async def on_system_message(self, message: Any) -> None:
        pass

    async def prompt_choice(
        self, _title: str, _text: str, choices: list[tuple[str, str]]
    ) -> str | None:
        return choices[0][0] if choices else None

    async def prompt_input(self, _title: str, _text: str) -> str | None:
        return "mock_input"

    async def prompt_checklist(
        self,
        _title: str,
        _text: str,
        _choices: list[tuple[str, str]],
        checked: list[str],
        *,
        extra: str | None = None,  # noqa: ARG002
    ) -> tuple[str, list[str]] | None:
        return ("ok", checked)


def test_client_ignores_the_token_of_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKEN", "env-secret")
    client = OllamaClient(base_url=TEST_BASE_URL, token=None, timeout=TEST_TIMEOUT)
    assert "Authorization" not in client._build_headers()  # noqa: SLF001


def test_client_sends_authorization_with_token() -> None:
    client = OllamaClient(base_url=TEST_BASE_URL, token="secret", timeout=TEST_TIMEOUT)  # noqa: S106
    assert client._build_headers()["Authorization"] == "Bearer secret"  # noqa: SLF001


class RecordingEvents(MockUIHandler):
    """UI handler recording the prompts and context warnings it receives."""

    def __init__(self) -> None:
        """Start with no prompt and no warning."""
        super().__init__()
        self.prompts: list[dict[str, Any]] = []
        self.warnings: list[tuple[int, int]] = []

    async def on_prompt(self, payload: dict[str, Any]) -> None:
        self.prompts.append(payload)

    async def on_context_warning(self, used: int, limit: int) -> None:
        self.warnings.append((used, limit))


def _client_replying(
    monkeypatch: pytest.MonkeyPatch, prompt_eval_count: int, **kwargs: Any
) -> OllamaClient:
    """A client whose non-streaming requests get a reply with this prompt token count."""

    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, Any]:
            return {"message": {"content": "ok"}, "prompt_eval_count": prompt_eval_count}

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
    return OllamaClient(base_url=TEST_BASE_URL, token="t", timeout=TEST_TIMEOUT, **kwargs)  # noqa: S106


@pytest.mark.asyncio
async def test_client_shows_the_exact_payload_only_when_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = [{"role": "user", "content": "hi"}]
    for show_prompt, expected in ((True, 1), (False, 0)):
        client = _client_replying(monkeypatch, 1, show_prompt=show_prompt, num_ctx=100)
        events = RecordingEvents()
        client.events = events
        await client.chat(messages=messages, model="m", stream=False)
        assert len(events.prompts) == expected
    client = _client_replying(monkeypatch, 1, show_prompt=True, num_ctx=100)
    client.events = events = RecordingEvents()
    await client.chat(messages=messages, model="m", stream=False)
    assert events.prompts[0]["messages"] == messages
    assert events.prompts[0]["options"] == {"num_ctx": 100}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("prompt_eval_count", "text", "warnings"),
    [
        (50, "hi", []),
        (95, "hi", [(95, 100)]),
        (0, "x" * 400, [(100, 100)]),
    ],
)
async def test_client_warns_when_the_prompt_nears_the_context_window(
    monkeypatch: pytest.MonkeyPatch,
    prompt_eval_count: int,
    text: str,
    warnings: list[tuple[int, int]],
) -> None:
    client = _client_replying(monkeypatch, prompt_eval_count, num_ctx=100)
    client.events = events = RecordingEvents()
    await client.chat(messages=[{"role": "user", "content": text}], stream=False)
    assert events.warnings == warnings


@pytest.mark.asyncio
async def test_client_does_not_warn_without_a_context_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client_replying(monkeypatch, 10**6)
    client.events = events = RecordingEvents()
    await client.chat(messages=[{"role": "user", "content": "hi"}], stream=False)
    assert events.warnings == []


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("num_ctx", "options", "expected_options"),
    [
        (None, None, None),
        (8192, None, {"num_ctx": 8192}),
        (8192, {"temperature": 0}, {"num_ctx": 8192, "temperature": 0}),
        (None, {"temperature": 0}, {"temperature": 0}),
    ],
)
async def test_client_chat_sends_options(
    monkeypatch: pytest.MonkeyPatch,
    num_ctx: int | None,
    options: dict[str, Any] | None,
    expected_options: dict[str, Any] | None,
) -> None:
    sent: dict[str, Any] = {}

    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, Any]:
            return {"message": {"content": "ok"}, "done_reason": "stop"}

    class MockAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def post(self, *_args: Any, **kwargs: Any) -> MockResponse:
            sent.update(kwargs["json"])
            return MockResponse()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    client = OllamaClient(base_url=TEST_BASE_URL, token=None, timeout=TEST_TIMEOUT, num_ctx=num_ctx)
    schema = {"type": "object"}
    await client.chat(
        messages=[{"role": "user", "content": "hi"}],
        stream=False,
        response_format=schema,
        options=options,
    )

    assert sent.get("options") == expected_options
    assert sent["format"] == schema


@pytest.mark.asyncio
async def test_client_chat_sends_client_temperature_and_top_p(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: dict[str, Any] = {}

    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, Any]:
            return {"message": {"content": "ok"}, "done_reason": "stop"}

    class MockAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def post(self, *_args: Any, **kwargs: Any) -> MockResponse:
            sent.update(kwargs["json"])
            return MockResponse()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    client = OllamaClient(
        base_url=TEST_BASE_URL,
        token=None,
        timeout=TEST_TIMEOUT,
        num_ctx=4096,
        temperature=0.8,
        top_p=0.95,
    )
    await client.chat(messages=[{"role": "user", "content": "hi"}], stream=False)

    assert sent.get("options") == {"num_ctx": 4096, "temperature": 0.8, "top_p": 0.95}

    # Now verify explicit options override client defaults (like PLAN_OPTIONS overrides temperature)
    sent.clear()
    await client.chat(
        messages=[{"role": "user", "content": "hi"}],
        stream=False,
        options={"temperature": 0},
    )
    assert sent.get("options") == {"num_ctx": 4096, "temperature": 0, "top_p": 0.95}
