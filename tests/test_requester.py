"""Tests for the ``sensai.requester`` module."""

import pytest
import requests

from sensai import requester


def test_make_request_returns_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock the requests.post method to return a mock response
    class MockResponse:
        def __init__(self, json_data, status_code):
            self._json_data = json_data
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code != 200:
                raise Exception("HTTP Error")

        def json(self):
            return self._json_data

    def mock_post(url, headers, data, stream, timeout):
        return MockResponse({"response": "This is a mock response."}, 200)

    monkeypatch.setattr(requests, "post", mock_post)

    url = "https://api.example.com/sensei"
    payload = {"prompt": "Hello, Sensei!"}
    headers = {"Authorization": "Bearer test_token"}

    response = requester.make_request(url, payload, headers)

    assert response == {"response": "This is a mock response."}


def test_make_request_raises_exception_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock the requests.post method to return a mock response with an error status code
    class MockResponse:
        def __init__(self, status_code):
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code != 200:
                raise Exception("HTTP Error")

    def mock_post(url, headers, data, stream, timeout):
        return MockResponse(500)

    monkeypatch.setattr(requests, "post", mock_post)

    url = "https://api.example.com/sensei"
    payload = {"prompt": "Hello, Sensei!"}
    headers = {"Authorization": "Bearer test_token"}

    with pytest.raises(Exception) as excinfo:
        requester.make_request(url, payload, headers)

    assert "HTTP Error" in str(excinfo.value)


def test_make_request_without_headers_skips_header_merge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MockResponse:
        def __init__(self, json_data, status_code):
            self._json_data = json_data
            self.status_code = status_code

        def raise_for_status(self):
            pass

        def json(self):
            return self._json_data

    captured_headers = {}

    def mock_post(url, headers, data, stream, timeout):
        captured_headers.update(headers)
        return MockResponse({"response": "ok"}, 200)

    monkeypatch.setattr(requests, "post", mock_post)

    response = requester.make_request("https://api.example.com/sensei", {"prompt": "hi"})

    assert response == {"response": "ok"}
    assert captured_headers == {"Content-Type": "application/json"}


def test_make_request_streaming_returns_defaults_when_no_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MockResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def iter_lines(self):
            return iter([])

    def mock_post(url, headers, data, stream, timeout):
        return MockResponse()

    monkeypatch.setattr(requests, "post", mock_post)

    response = requester.make_request(
        "https://api.example.com/sensei", {"prompt": "hi"}, stream=True
    )

    assert response["response"] == ""
    assert response["stop_reason"] == ""
    assert response["eval_count"] == 0
    assert response["prompt_eval_count"] == 0
    assert response["token_used"] == 0
    assert response["context"] == ""
    assert response["status_code"] == 200


def test_make_request_streaming_skips_empty_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def iter_lines(self):
            return iter(
                [
                    b"",
                    b'{"response": "Hello"}',
                    (
                        b'{"response": " world", "done": true, "done_reason": "stop", '
                        b'"eval_count": 5, "prompt_eval_count": 3, "context": [1, 2], '
                        b'"total_duration": 42}'
                    ),
                ]
            )

    def mock_post(url, headers, data, stream, timeout):
        return MockResponse()

    monkeypatch.setattr(requests, "post", mock_post)

    response = requester.make_request(
        "https://api.example.com/sensei", {"prompt": "hi"}, stream=True
    )

    assert response["response"] == "Hello world"
    assert response["stop_reason"] == "stop"
    assert response["eval_count"] == 5
    assert response["prompt_eval_count"] == 3
    assert response["token_used"] == 8
    assert response["context"] == [1, 2]
    assert response["total_duration"] == 42


def test_get_sensei_response_returns_expected_response(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock the make_request function to return a mock response
    def mock_make_request(url, payload, headers, stream):
        return {"response": "This is a mock response."}

    monkeypatch.setattr(requester, "make_request", mock_make_request)
    monkeypatch.setenv("TOKEN", "test_token")

    prompt = "Hello, Sensei! Can you tell me a joke?"
    model = "llama3.2"
    tools = None

    response = requester.get_sensei_response(prompt, model, tools)

    assert response == {"response": "This is a mock response."}


def test_get_sensei_response_raises_value_error_when_token_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulate a missing token in the environment
    monkeypatch.delenv("TOKEN", raising=False)

    prompt = "Hello, Sensei! Can you tell me a joke?"
    model = "llama3.2"
    tools = None

    with pytest.raises(ValueError) as excinfo:
        requester.get_sensei_response(prompt, model, tools)

    assert "API token not found in environment variables." in str(excinfo.value)


def test_get_sensei_response_calls_make_request_without_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mock the make_request function to return a mock response
    called = {"called": False}

    def mock_make_request(url, payload, headers, stream):
        called["called"] = True
        assert url == "https://ollama.tanouminou.com/api/generate"
        assert payload["prompt"] == "Hello, Sensei! Can you tell me a joke?"
        assert payload["model"] == "llama3.2"
        assert payload["tools"] == []
        assert payload["stream"] is True
        assert headers is not None  # Ensure headers are provided
        return {"response": "This is a mock response."}

    monkeypatch.setattr(requester, "make_request", mock_make_request)
    monkeypatch.setenv("TOKEN", "test_token")

    prompt = "Hello, Sensei! Can you tell me a joke?"
    model = "llama3.2"
    tools = None

    response = requester.get_sensei_response(prompt, model, tools)

    assert called["called"]
    assert response == {"response": "This is a mock response."}
