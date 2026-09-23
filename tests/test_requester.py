"""Tests for the ``sensai.requester`` module."""

import json
from typing import Any

import pytest
import requests

from sensai import requester


def test_get_buffered_response_joins_and_clears_buffer() -> None:
    requester.streaming_response_buffer.extend(["Hello", " ", "world"])

    result = requester.get_buffered_response()

    assert result == "Hello world"
    assert requester.streaming_response_buffer == []


class MockResponse:
    """Minimal stand-in for :class:`requests.Response` used across these tests."""

    def __init__(
        self,
        json_data: dict[str, Any] | None = None,
        status_code: int = 200,
        lines: list[bytes] | None = None,
    ) -> None:
        """Initialize the mock response with canned data."""
        self._json_data = json_data
        self.status_code = status_code
        self._lines = lines or []

    def raise_for_status(self) -> None:
        if self.status_code != 200:
            raise requests.exceptions.HTTPError("HTTP Error")

    def json(self) -> dict[str, Any] | None:
        return self._json_data

    def iter_lines(self):
        return iter(self._lines)


def test_make_request_returns_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_post(url, headers, data, stream, timeout):
        return MockResponse({"message": {"content": "This is a mock response."}})

    monkeypatch.setattr(requests, "post", mock_post)

    response = requester.make_request(
        "https://api.example.com/sensei",
        {"messages": [{"role": "user", "content": "Hello, Sensei!"}]},
        {"Authorization": "Bearer test_token"},
    )

    assert response == {"message": {"content": "This is a mock response."}}


def test_make_request_raises_exception_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_post(url, headers, data, stream, timeout):
        return MockResponse(status_code=500)

    monkeypatch.setattr(requests, "post", mock_post)

    with pytest.raises(requests.exceptions.HTTPError, match="HTTP Error"):
        requester.make_request(
            "https://api.example.com/sensei",
            {"messages": []},
            {"Authorization": "Bearer test_token"},
        )


def test_make_request_without_headers_skips_header_merge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_headers = {}

    def mock_post(url, headers, data, stream, timeout):
        captured_headers.update(headers)
        return MockResponse({"message": {"content": "ok"}})

    monkeypatch.setattr(requests, "post", mock_post)

    response = requester.make_request("https://api.example.com/sensei", {"messages": []})

    assert response == {"message": {"content": "ok"}}
    assert captured_headers == {"Content-Type": "application/json"}


def test_make_request_streaming_returns_defaults_when_no_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_post(url, headers, data, stream, timeout):
        return MockResponse(lines=[])

    monkeypatch.setattr(requests, "post", mock_post)

    response = requester.make_request(
        "https://api.example.com/sensei", {"messages": []}, stream=True
    )

    assert response["response"] == ""
    assert response["stop_reason"] == ""
    assert response["eval_count"] == 0
    assert response["prompt_eval_count"] == 0
    assert response["token_used"] == 0
    assert response["tool_calls"] == []
    assert response["status_code"] == 200


def test_make_request_streaming_skips_empty_lines_and_aggregates_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_post(url, headers, data, stream, timeout):
        return MockResponse(
            lines=[
                b"",
                b'{"message": {"content": "Hello"}}',
                (
                    b'{"message": {"content": " world"}, "done": true, '
                    b'"done_reason": "stop", "eval_count": 5, "prompt_eval_count": 3, '
                    b'"total_duration": 42}'
                ),
            ]
        )

    monkeypatch.setattr(requests, "post", mock_post)

    response = requester.make_request(
        "https://api.example.com/sensei", {"messages": []}, stream=True
    )

    assert response["response"] == "Hello world"
    assert response["stop_reason"] == "stop"
    assert response["eval_count"] == 5
    assert response["prompt_eval_count"] == 3
    assert response["token_used"] == 8
    assert response["total_duration"] == 42


def test_make_request_streaming_collects_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    tool_call = {
        "id": "call_1",
        "function": {"name": "get_temperature", "arguments": {"city": "Paris"}},
    }

    def mock_post(url, headers, data, stream, timeout):
        return MockResponse(
            lines=[
                json_line({"message": {"content": "", "tool_calls": [tool_call]}}),
                json_line({"message": {"content": ""}, "done": True, "done_reason": "stop"}),
            ]
        )

    monkeypatch.setattr(requests, "post", mock_post)

    response = requester.make_request(
        "https://api.example.com/sensei", {"messages": []}, stream=True
    )

    assert response["tool_calls"] == [tool_call]


def json_line(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload).encode()


def test_get_sensei_response_raises_value_error_when_token_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TOKEN", raising=False)

    with pytest.raises(ValueError) as excinfo:
        requester.get_sensei_response("Hello, Sensei!")

    assert "API token not found in environment variables." in str(excinfo.value)


def test_get_sensei_response_raises_value_error_without_prompt_or_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOKEN", "test_token")

    with pytest.raises(ValueError) as excinfo:
        requester.get_sensei_response()

    assert "Either prompt or messages must be provided." in str(excinfo.value)


def test_get_sensei_response_builds_messages_from_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def mock_make_request(url, payload, headers=None, *, stream=False, timeout=300):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return {"response": "hi", "tool_calls": [], "messages": payload["messages"]}

    monkeypatch.setattr(requester, "make_request", mock_make_request)
    monkeypatch.setenv("TOKEN", "test_token")

    response = requester.get_sensei_response("Hello, Sensei! Can you tell me a joke?")

    assert captured["url"] == "https://ollama.tanouminou.com/api/chat"
    assert captured["payload"]["messages"] == [
        {"role": "user", "content": "Hello, Sensei! Can you tell me a joke?"}
    ]
    assert captured["payload"]["model"] == "llama3.2"
    assert captured["payload"]["tools"] == []
    assert captured["payload"]["stream"] is True
    assert captured["headers"] == {"Authorization": "Bearer test_token"}
    assert response["response"] == "hi"


def test_get_sensei_response_uses_messages_when_given(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def mock_make_request(url, payload, headers=None, *, stream=False, timeout=300):
        captured["payload"] = payload
        return {"response": "hi", "tool_calls": [], "messages": payload["messages"]}

    monkeypatch.setattr(requester, "make_request", mock_make_request)
    monkeypatch.setenv("TOKEN", "test_token")

    history = [
        {"role": "user", "content": "hey"},
        {"role": "assistant", "content": "yo"},
    ]
    requester.get_sensei_response(messages=history)

    assert captured["payload"]["messages"] == history


def test_get_sensei_response_formats_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTool:
        def define(self) -> dict[str, Any]:
            return {"type": "function", "function": {"name": "noop"}}

    captured: dict[str, Any] = {}

    def mock_make_request(url, payload, headers=None, *, stream=False, timeout=300):
        captured["payload"] = payload
        return {"response": "hi", "tool_calls": [], "messages": payload["messages"]}

    monkeypatch.setattr(requester, "make_request", mock_make_request)
    monkeypatch.setenv("TOKEN", "test_token")

    requester.get_sensei_response("hello", tools=[FakeTool()])

    assert captured["payload"]["tools"] == [{"type": "function", "function": {"name": "noop"}}]


def test_call_tool_returns_response_unchanged_without_tools() -> None:
    response = {"response": "hi"}

    result = requester.call_tool([{"function": {"name": "x"}}], response, [], tools=None)

    assert result is response


def test_call_tool_returns_response_unchanged_without_toolcalls() -> None:
    response = {"response": "hi"}

    result = requester.call_tool([], response, [], tools=[object()])

    assert result is response


def test_call_tool_executes_matching_tool_and_recurses(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTool:
        name = "get_temperature"

        def execute(self, **kwargs: Any) -> str:
            return f"It is 20°C in {kwargs['city']}."

    tool_call = {
        "id": "call_1",
        "function": {"name": "get_temperature", "arguments": {"city": "Paris"}},
    }
    response = {"response": "", "model": "llama3.2"}
    messages = [{"role": "user", "content": "What's the temperature in Paris?"}]

    captured: dict[str, Any] = {}

    def mock_get_sensei_response(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"response": "It is 20°C in Paris.", "tool_calls": []}

    monkeypatch.setattr(requester, "get_sensei_response", mock_get_sensei_response)

    result = requester.call_tool([tool_call], response, messages, tools=[FakeTool()])

    assert result == {"response": "It is 20°C in Paris.", "tool_calls": []}
    assert captured["model"] == "llama3.2"
    assert captured["tools"][0].name == "get_temperature"
    assert captured["stream"] is True
    conversation = captured["messages"]
    assert conversation[0] == messages[0]
    assert conversation[1] == {"role": "assistant", "content": "", "tool_calls": [tool_call]}
    assert conversation[2] == {"role": "tool", "content": "It is 20°C in Paris."}


def test_call_tool_serializes_non_string_tool_results(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTool:
        name = "get_temperature"

        def execute(self, **kwargs: Any) -> dict[str, Any]:
            return {"city": kwargs["city"], "temp_c": 20}

    tool_call = {
        "id": "call_1",
        "function": {"name": "get_temperature", "arguments": {"city": "Paris"}},
    }
    response = {"response": "", "model": "llama3.2"}

    captured: dict[str, Any] = {}

    def mock_get_sensei_response(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(requester, "get_sensei_response", mock_get_sensei_response)

    requester.call_tool([tool_call], response, [], tools=[FakeTool()])

    assert captured["messages"][-1] == {
        "role": "tool",
        "content": '{"city": "Paris", "temp_c": 20}',
    }


def test_call_tool_skips_unmatched_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTool:
        name = "get_temperature"

        def execute(self, **_kwargs: Any) -> str:
            return "unused"

    tool_call = {"id": "call_1", "function": {"name": "unknown_tool", "arguments": {}}}
    response = {"response": "", "model": "llama3.2"}

    captured: dict[str, Any] = {}

    def mock_get_sensei_response(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(requester, "get_sensei_response", mock_get_sensei_response)

    requester.call_tool([tool_call], response, [], tools=[FakeTool()])

    conversation = captured["messages"]
    assert conversation == [{"role": "assistant", "content": "", "tool_calls": [tool_call]}]


def test_get_sensei_response_end_to_end_with_tool_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeTool:
        name = "get_temperature"

        def define(self) -> dict[str, Any]:
            return {"type": "function", "function": {"name": "get_temperature"}}

        def execute(self, **kwargs: Any) -> str:
            return f"It is 20°C in {kwargs['city']}."

    tool_call = {
        "id": "call_1",
        "function": {"name": "get_temperature", "arguments": {"city": "Paris"}},
    }
    calls: list[dict[str, Any]] = []

    def mock_make_request(url, payload, headers=None, *, stream=False, timeout=300):
        calls.append(payload)
        if len(calls) == 1:
            return {"response": "", "tool_calls": [tool_call], "messages": payload["messages"]}
        return {
            "response": "It is 20°C in Paris.",
            "tool_calls": [],
            "messages": payload["messages"],
        }

    monkeypatch.setattr(requester, "make_request", mock_make_request)
    monkeypatch.setenv("TOKEN", "test_token")

    response = requester.get_sensei_response("What's the temperature in Paris?", tools=[FakeTool()])

    assert len(calls) == 2
    assert response["response"] == "It is 20°C in Paris."
    second_call_messages = calls[1]["messages"]
    assert second_call_messages[-1] == {"role": "tool", "content": "It is 20°C in Paris."}
