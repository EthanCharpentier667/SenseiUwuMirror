"""Tests for the ``sensai.tools.temperature_example`` module."""

from typing import Any

import httpx
import pytest

from sensai.tools.temperature_example import TempToolExample

WTTR_PAYLOAD = {
    "current_condition": [
        {
            "temp_C": "20",
            "humidity": "50",
            "windspeedKmph": "15",
            "weatherDesc": [{"value": "Sunny"}],
        }
    ]
}


class MockGetResponse:
    """Minimal stand-in for :meth:`httpx.get`'s return value."""

    def __init__(self, payload: dict[str, Any]) -> None:
        """Initialize the mock response with a canned payload."""
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


def test_define_returns_openai_style_schema() -> None:
    tool = TempToolExample()

    assert tool.define() == {
        "type": "function",
        "function": {
            "name": "get_temperature",
            "description": "Get the current temperature for a city.",
            "parameters": {
                "type": "object",
                "required": ["city"],
                "properties": {"city": {"type": "string", "description": "The name of the city"}},
            },
        },
    }


def test_execute_fetches_and_formats_weather(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request: dict[str, Any] = {}

    def mock_get(url: str, *, timeout: float, follow_redirects: bool = False) -> MockGetResponse:
        captured_request["url"] = url
        captured_request["timeout"] = timeout
        captured_request["follow_redirects"] = follow_redirects
        return MockGetResponse(WTTR_PAYLOAD)

    monkeypatch.setattr(httpx, "get", mock_get)

    tool = TempToolExample()
    result = tool.execute(city="Paris")

    assert captured_request["url"] == "https://wttr.in/Paris?format=j1"
    assert captured_request["timeout"] == 10
    assert captured_request["follow_redirects"] is True
    assert result == (
        "The current temperature in Paris is 20°C. The weather is Sunny. "
        "The humidity is 50% and the wind speed is 15 km/h."
    )


def test_execute_defaults_to_unknown_city_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_get(*_args: Any, **_kwargs: Any) -> MockGetResponse:
        return MockGetResponse(WTTR_PAYLOAD)

    monkeypatch.setattr(httpx, "get", mock_get)

    tool = TempToolExample()
    result = tool.execute()

    assert "Unknown City" in result
