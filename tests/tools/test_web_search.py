"""Tests for the ``sensai.tools.web_search`` module."""

import json
from typing import Any

import pytest
import requests

import sensai.tools.web_search as web_search_module
from sensai.tools.web_search import DEFAULT_TIMEOUT, WebSearch, web_search

SEARCH_PAYLOAD = {
    "results": [
        {
            "title": "Squeezie",
            "url": "https://example.com/squeezie",
            "content": "Lucas Hauchard is known as Squeezie.",
        }
    ]
}


class MockPostResponse:
    """Minimal stand-in for :meth:`requests.post`'s return value."""

    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        """Initialize the mock response with a status and JSON payload."""
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        """Return the configured JSON payload."""
        return self._payload


def test_define_returns_openai_style_schema() -> None:
    tool = WebSearch()

    assert tool.define() == {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Perform a web search for the given query.",
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {"query": {"type": "string", "description": "The search query"}},
            },
        },
    }


def test_execute_forwards_query_and_formats_result(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_query: dict[str, str] = {}

    def mock_web_search(query: str) -> dict[str, Any]:
        captured_query["query"] = query
        return SEARCH_PAYLOAD

    monkeypatch.setattr(web_search_module, "web_search", mock_web_search)

    result = WebSearch().execute(query="Lucas Hauchard")

    assert captured_query["query"] == "Lucas Hauchard"
    assert result == f"Web search result for 'Lucas Hauchard': {SEARCH_PAYLOAD}"


def test_web_search_sends_authenticated_request(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request: dict[str, Any] = {}

    def mock_post(
        url: str,
        *,
        headers: dict[str, str],
        data: str,
        timeout: int,
    ) -> MockPostResponse:
        captured_request.update({"url": url, "headers": headers, "data": data, "timeout": timeout})
        return MockPostResponse(200, SEARCH_PAYLOAD)

    monkeypatch.setenv("API_TOKEN", "test-api-token")
    monkeypatch.setattr(requests, "post", mock_post)

    result = web_search("Lucas Hauchard")

    assert result == SEARCH_PAYLOAD
    assert captured_request == {
        "url": "https://ollama.com/api/web_search",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-api-token",
        },
        "data": json.dumps({"query": "Lucas Hauchard"}),
        "timeout": DEFAULT_TIMEOUT,
    }


def test_web_search_returns_unavailable_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_TOKEN", raising=False)

    def unexpected_post(*_args: Any, **_kwargs: Any) -> MockPostResponse:
        pytest.fail("requests.post must not be called without an API token")

    monkeypatch.setattr(requests, "post", unexpected_post)

    assert web_search("Lucas Hauchard") == {"message": "Web search is not available."}


def test_web_search_returns_failure_for_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_post(
        _url: str,
        *,
        headers: dict[str, str],
        data: str,
        timeout: int,
    ) -> MockPostResponse:
        return MockPostResponse(500, {"error": "internal server error"})

    monkeypatch.setenv("API_TOKEN", "test-api-token")
    monkeypatch.setattr(requests, "post", mock_post)

    assert web_search("Lucas Hauchard") == {"message": "Web search failed."}
