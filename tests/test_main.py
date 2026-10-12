"""Tests for the ``sensai`` package entry point."""

from typing import Any

import pytest

from sensai import main
from sensai.agent import Agent
from sensai.client import Response
from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import Profile
from sensai.data.session.session import Session
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


async def _fake_retrieve_chunks(*_args: Any, **_kwargs: Any) -> list[Any]:
    return []


async def _fake_maybe_compress_session(*_args: Any, **_kwargs: Any) -> Session:
    return _make_session()


def _patch_main_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _mock_auth(*args: Any, **kwargs: Any) -> Profile:
        return _make_profile()

    monkeypatch.setattr("sys.argv", ["sensai"])
    monkeypatch.setattr("sensai.setup_database", lambda *args, **kwargs: _FakeDatabase())
    monkeypatch.setattr("sensai.authenticate_user", _mock_auth)
    monkeypatch.setattr("sensai.get_or_create_session", lambda *args, **kwargs: _make_session())
    monkeypatch.setattr("sensai.ui.app.update_session", lambda *args, **kwargs: _make_session())
    monkeypatch.setattr("sensai.ui.app.maybe_compress_session", _fake_maybe_compress_session)
    monkeypatch.setattr("sensai.ui.app.retrieve_chunks", _fake_retrieve_chunks)


def test_main_greets_the_profile_and_exits_on_keyboard_interrupt(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_main_dependencies(monkeypatch)

    async def fake_prompt_async(*args: Any, **kwargs: Any) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("sensai.ui.app.PromptSession.prompt_async", fake_prompt_async)

    main()

    captured = capsys.readouterr()
    assert "Hello Default Profile! Welcome to Sensai." in captured.out
    assert "Program terminated by user." in captured.out


def test_main_calls_agent_run_for_each_input(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    async def mock_run(
        self: Agent,
        prompt: str | None = None,
        *,
        messages: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
    ) -> Response:
        calls.append({"prompt": prompt, "messages": messages, "tools": self.tools})
        assert self.model == "llama3.2"
        assert getattr(self, "trust_level", None) == "none"
        return _make_response()

    inputs = iter(["hello there", "second question"])

    async def fake_prompt_async(*args: Any, **kwargs: Any) -> str:
        try:
            return next(inputs)
        except StopIteration as exc:
            raise KeyboardInterrupt from exc

    _patch_main_dependencies(monkeypatch)
    monkeypatch.setattr(Agent, "run", mock_run)
    monkeypatch.setattr("sensai.ui.app.PromptSession.prompt_async", fake_prompt_async)

    main()

    assert len(calls) == 2
    assert calls[0]["prompt"] is None
    assert calls[0]["messages"] == [{"role": "user", "content": "hello there"}]
    first_turn_tools = calls[0]["tools"]
    assert len(first_turn_tools) == 3
    assert isinstance(first_turn_tools[0], WebSearch)
    assert isinstance(first_turn_tools[1], TempToolExample)

    assert calls[1]["prompt"] is None
    assert calls[1]["messages"] == [{"role": "user", "content": "second question"}]
    second_turn_tools = calls[1]["tools"]
    assert len(second_turn_tools) == 3
