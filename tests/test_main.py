"""Tests for the ``sensai`` package entry point."""

from typing import Any

import pytest

from sensai import main
from sensai.data.profile_manager import Profile
from sensai.data.session.session import Session
from sensai.requester import Response


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
    return Profile(name="Default Profile", id=1)


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
    monkeypatch.setattr("sensai.create_profile", _make_profile)
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
        calls.append({"prompt": prompt, "messages": messages})
        assert model == "llama3.2"
        assert stream is True
        assert tools is None
        return _make_response()

    monkeypatch.setattr("sensai.Database", _FakeDatabase)
    monkeypatch.setattr("sensai.create_profile", _make_profile)
    monkeypatch.setattr("sensai.create_new_session", lambda *args, **kwargs: _make_session())
    monkeypatch.setattr("sensai.update_session", lambda *args, **kwargs: _make_session())
    monkeypatch.setattr("sensai.get_sensei_response", mock_get_sensei_response)
    main()

    assert calls[0] == {
        "prompt": "Hello, Sensei! How are you doing today?",
        "messages": None,
    }
    assert calls[1] == {
        "prompt": None,
        "messages": [
            {
                "role": "user",
                "content": ("Can you summarize the previous response and demands in one sentence?"),
            }
        ],
    }
