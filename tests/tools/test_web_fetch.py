"""Tests for the ``sensai.tools.web_fetch`` module."""

from typing import Any
from unittest.mock import Mock

import httpx
import pytest

import sensai.tools.web_fetch as web_fetch_module
from sensai.tools.web_fetch import DEFAULT_TIMEOUT, WebFetch, fetch_url

PAGE_URL = "https://example.com/game"
FETCH_PAYLOAD = {
    "title": "Game rules",
    "content": "Listen to the clip and guess the song.",
    "links": ["https://example.com/help"],
}


def test_define_returns_openai_style_schema() -> None:
    tool = WebFetch()

    assert tool.define() == {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": tool.description,
            "parameters": {
                "type": "object",
                "required": ["url"],
                "properties": {"url": {"type": "string", "description": "The URL to fetch"}},
            },
        },
    }


def test_execute_forwards_url_and_returns_fetch_result(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_fetch = Mock(return_value=FETCH_PAYLOAD)
    monkeypatch.setattr(web_fetch_module, "fetch_url", mock_fetch)

    result = WebFetch().execute(url=PAGE_URL)

    mock_fetch.assert_called_once_with(PAGE_URL)
    assert result == FETCH_PAYLOAD


def test_execute_uses_default_when_url_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_fetch = Mock(return_value={"message": "Web fetch failed."})
    monkeypatch.setattr(web_fetch_module, "fetch_url", mock_fetch)

    result = WebFetch().execute()

    mock_fetch.assert_called_once_with("Unknown URL")
    assert result == {"message": "Web fetch failed."}


def test_fetch_url_sends_authenticated_request(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_post = Mock(return_value=httpx.Response(200, json=FETCH_PAYLOAD))
    monkeypatch.setenv("API_TOKEN", "test-api-token")
    monkeypatch.setattr(httpx, "post", mock_post)

    result = fetch_url(PAGE_URL)

    assert result == FETCH_PAYLOAD
    mock_post.assert_called_once_with(
        "https://ollama.com/api/web_fetch",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer test-api-token",
        },
        json={"url": PAGE_URL},
        timeout=DEFAULT_TIMEOUT,
    )


@pytest.mark.parametrize("token", [None, ""])
def test_fetch_url_skips_request_without_token(
    monkeypatch: pytest.MonkeyPatch,
    token: str | None,
) -> None:
    if token is None:
        monkeypatch.delenv("API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("API_TOKEN", token)
    mock_post = Mock()
    monkeypatch.setattr(httpx, "post", mock_post)

    assert fetch_url(PAGE_URL) == {"message": "Web search is not available."}
    mock_post.assert_not_called()


@pytest.mark.parametrize("status_code", [400, 401, 404, 429, 500])
def test_fetch_url_returns_failure_without_decoding_error_body(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
) -> None:
    # Error responses may be HTML rather than JSON.
    mock_post = Mock(return_value=httpx.Response(status_code, text="Service unavailable"))
    monkeypatch.setenv("API_TOKEN", "test-api-token")
    monkeypatch.setattr(httpx, "post", mock_post)

    assert fetch_url(PAGE_URL) == {"message": "Web fetch failed."}


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "Empty page", "content": "", "links": None},
        {"title": "Songless", "content": "@layer reset{body{margin:0}}", "links": None},
    ],
)
def test_fetch_url_preserves_api_content(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any],
) -> None:
    # Fetching currently forwards content; it does not clean CSS or invent missing text.
    mock_post = Mock(return_value=httpx.Response(200, json=payload))
    monkeypatch.setenv("API_TOKEN", "test-api-token")
    monkeypatch.setattr(httpx, "post", mock_post)

    assert fetch_url(PAGE_URL) == payload


@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ConnectError])
def test_fetch_url_propagates_network_errors(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[httpx.RequestError],
) -> None:
    error = error_type("Connection failed", request=httpx.Request("POST", PAGE_URL))
    mock_post = Mock(side_effect=error)
    monkeypatch.setenv("API_TOKEN", "test-api-token")
    monkeypatch.setattr(httpx, "post", mock_post)

    with pytest.raises(error_type, match="Connection failed"):
        fetch_url(PAGE_URL)
