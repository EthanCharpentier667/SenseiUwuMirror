"""Tests for the ``sensai.require_approval`` module."""

import json
from typing import Any

import pytest

from sensai.require_approval import _display_tool_call, _get_user_choice, require_approval


def test_display_tool_call_prints_name(capsys: pytest.CaptureFixture[str]) -> None:
    _display_tool_call("web_search", {"query": "weather Paris"})
    captured = capsys.readouterr()
    assert "web_search" in captured.out


def test_display_tool_call_prints_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    arguments = {"query": "weather Paris"}
    _display_tool_call("web_search", arguments)
    captured = capsys.readouterr()
    assert json.dumps(arguments, indent=2, ensure_ascii=False) in captured.out


def test_get_user_choice_returns_stripped_lowercase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "  Y  ")
    assert _get_user_choice() == "y"


@pytest.mark.parametrize("answer", ["y", "yes", "o", "oui", ""])
def test_require_approval_returns_true_on_yes_variants(
    answer: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("builtins.input", lambda _: answer)
    monkeypatch.setattr("sensai.require_approval._display_tool_call", lambda *_: None)
    assert require_approval("tool", {}) is True


@pytest.mark.parametrize("answer", ["n", "no", "non", "cancel", "nope"])
def test_require_approval_returns_false_on_no_variants(
    answer: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("builtins.input", lambda _: answer)
    monkeypatch.setattr("sensai.require_approval._display_tool_call", lambda *_: None)
    assert require_approval("tool", {}) is False


def test_require_approval_calls_display_with_correct_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def mock_display(name: str, arguments: dict[str, Any]) -> None:
        captured["name"] = name
        captured["arguments"] = arguments

    monkeypatch.setattr("sensai.require_approval._display_tool_call", mock_display)
    monkeypatch.setattr("builtins.input", lambda _: "y")

    require_approval("web_search", {"query": "Paris"})

    assert captured["name"] == "web_search"
    assert captured["arguments"] == {"query": "Paris"}
