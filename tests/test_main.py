"""Tests for the ``sensai`` package entry point."""

from typing import Any

import pytest

from sensai import main


def test_main_prints_greeting(capsys: pytest.CaptureFixture[str]) -> None:
    main()
    captured = capsys.readouterr()
    assert "Hello from sensei-uwu-mirror!" in captured.out


def test_main_calls_get_sensei_response(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"called": False}

    def mock_get_sensei_response(
        prompt: str,
        model: str = "llama3.2",
        tools: list[Any] | None = None,
        *,
        stream: bool = True,
    ) -> dict[str, Any]:
        called["called"] = True
        assert prompt == "Hello, Sensei! Can you tell me a joke?"
        assert model == "llama3.2"
        assert tools is None
        assert stream is True
        return {"response": "This is a mock response."}

    monkeypatch.setattr("sensai.get_sensei_response", mock_get_sensei_response)
    main()
    assert called["called"]
