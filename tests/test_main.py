"""Tests for the ``sensai`` package entry point."""

from typing import Any

import pytest

from sensai import main
from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import Profile
from sensai.data.session.session import Session
from sensai.requester import Response
from sensai.tools.temperature_example import TempToolExample
from sensai.tools.web_search import WebSearch


def _make_response(text: str = "This is a mock response.") -> Response:
    return Response(
        response=text,
        respond_time=0.0,
        request_time=0.0,
        total_duration=0,
        model="llama3.2",
        tools=[],
        messages=[],
        prompt_eval_count=0,
        eval_count=0,
        token_used=0,
        status_code=200,
        tool_calls=[],
        stop_reason="stop",
    )


def _make_session() -> Session:
    return Session(profile_id=1, name="test_session", id=1)


def _make_profile(*_args: Any, **_kwargs: Any) -> Profile:
    profile = Profile(name="Default Profile", password="hashed", id=1)  # noqa: S106
    ProfileManager.current_profile = profile
    return profile


class _FakeDatabase:
    """Stand-in for Database that never touches disk."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def initialize(self) -> None:
        pass


def test_main_prints_separators(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sensai.Database", _FakeDatabase)
    monkeypatch.setattr("sensai.create_new_profile", _make_profile)
    monkeypatch.setattr("sensai.add_preference", lambda *args, **kwargs: None)
    monkeypatch.setattr("sensai.add_instruction", lambda *args, **kwargs: None)
    monkeypatch.setattr("sensai.create_new_session", lambda *args, **kwargs: _make_session())
    monkeypatch.setattr("sensai.update_session", lambda *args, **kwargs: _make_session())
    monkeypatch.setattr("sensai.get_sensei_response", lambda *args, **kwargs: _make_response())
    main()
    captured = capsys.readouterr()
    assert captured.out.count("---------------") == 2


def test_main_calls_get_sensei_response(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def mock_get_sensei_response(
        prompt: str | None = None,
        model: str = "llama3.2",
        tools: list[Any] | None = None,
        *,
        messages: list[dict[str, Any]] | None = None,
        stream: bool = True,
    ) -> Response:
        calls.append({"prompt": prompt, "messages": messages, "tools": tools})
        assert model == "llama3.2"
        assert stream is True
        return _make_response()

    monkeypatch.setattr("sensai.Database", _FakeDatabase)
    monkeypatch.setattr("sensai.create_new_profile", _make_profile)
    monkeypatch.setattr("sensai.add_preference", lambda *args, **kwargs: None)
    monkeypatch.setattr("sensai.add_instruction", lambda *args, **kwargs: None)
    monkeypatch.setattr("sensai.create_new_session", lambda *args, **kwargs: _make_session())
    monkeypatch.setattr("sensai.update_session", lambda *args, **kwargs: _make_session())
    monkeypatch.setattr("sensai.get_sensei_response", mock_get_sensei_response)
    main()

    assert calls[0]["prompt"] is None
    assert calls[0]["messages"] == [
        {
            "role": "user",
            "content": "Hello, Sensei! How are you doing today? Who is sweetie fox?",
        }
    ]
    first_turn_tools = calls[0]["tools"]
    assert first_turn_tools is not None
    assert len(first_turn_tools) == 2
    assert isinstance(first_turn_tools[0], WebSearch)
    assert isinstance(first_turn_tools[1], TempToolExample)

    assert calls[1] == {
        "prompt": None,
        "messages": [{"role": "user", "content": "So what do you think about her ?"}],
        "tools": None,
    }
