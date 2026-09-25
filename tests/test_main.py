"""Tests for the ``sensai`` package entry point."""

from typing import Any

import pytest

from sensai import Agent, main
from sensai.tools.temperature_example import TempToolExample
from sensai.tools.web_search import WebSearch
from sensai.ui import CLIHandler


def test_main_prints_greeting(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def mock_run(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(Agent, "run", mock_run)
    main()
    captured = capsys.readouterr()
    assert "Hello from sensei-uwu-mirror!" in captured.out


def test_main_calls_agent_run(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"called": False}

    async def mock_run(self: Agent, prompt: str | None = None, **kwargs: Any) -> dict[str, Any]:
        called["called"] = True
        assert prompt == "Hello, Sensei! Who is Sweetie Fox ?"
        assert self.model == "llama3.2"
        assert self.human_in_the_loop is True
        assert len(self.tools) == 2
        assert isinstance(self.tools[0], WebSearch)
        assert isinstance(self.tools[1], TempToolExample)
        assert isinstance(self.ui_handler, CLIHandler)
        return {"response": "This is a mock response."}

    monkeypatch.setattr(Agent, "run", mock_run)
    main()
    assert called["called"]
