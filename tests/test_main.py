"""Tests for the ``sensai`` package entry point."""

from typing import Any

import pytest

from sensai import main
from sensai.events import AsyncUIHandler
from sensai.tools.temperature_example import TempToolExample
from sensai.tools.web_search import WebSearch


def test_main_prints_greeting(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def mock_get_sensei_response(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {}

    monkeypatch.setattr("sensai.get_sensei_response", mock_get_sensei_response)
    main()
    captured = capsys.readouterr()
    assert "Hello from sensei-uwu-mirror!" in captured.out


def test_main_calls_get_sensei_response(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"called": False}

    async def mock_get_sensei_response(  # noqa: PLR0913
        prompt: str,
        model: str = "llama3.2",
        tools: list[Any] | None = None,
        *,
        messages: list[dict[str, Any]] | None = None,
        human_in_the_loop: bool = False,
        ui_handler: AsyncUIHandler | None = None,
    ) -> dict[str, Any]:
        called["called"] = True
        assert prompt == "Hello, Sensei! Who is Sweetie Fox ?"
        assert model == "llama3.2"
        assert messages is None
        assert human_in_the_loop is True
        assert tools is not None
        assert len(tools) == 2
        assert isinstance(tools[0], WebSearch)
        assert isinstance(tools[1], TempToolExample)
        assert ui_handler is not None
        return {"response": "This is a mock response."}

    monkeypatch.setattr("sensai.get_sensei_response", mock_get_sensei_response)
    main()
    assert called["called"]
