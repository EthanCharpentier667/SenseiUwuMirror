"""Tests for the ``sensai.tool.temperature_example`` module."""

from typing import Any

import pytest
import requests

from sensai.tool.temperature_example import TempToolExample

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
    """Minimal stand-in for :meth:`requests.get`'s return value."""

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
    captured_url: dict[str, Any] = {}

    def mock_get(url: str, timeout: float) -> MockGetResponse:
        captured_url["url"] = url
        captured_url["timeout"] = timeout
        return MockGetResponse(WTTR_PAYLOAD)

    monkeypatch.setattr(requests, "get", mock_get)

    tool = TempToolExample()
    result = tool.execute(city="Paris")

    assert captured_url["url"] == "https://wttr.in/Paris?format=j1"
    assert result == (
        "The current temperature in Paris is 20°C. The weather is Sunny. "
        "The humidity is 50% and the wind speed is 15 km/h."
    )


def test_execute_defaults_to_unknown_city_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_get(url: str, timeout: float) -> MockGetResponse:
        return MockGetResponse(WTTR_PAYLOAD)

    monkeypatch.setattr(requests, "get", mock_get)

    tool = TempToolExample()
    result = tool.execute()

    assert "Unknown City" in result
