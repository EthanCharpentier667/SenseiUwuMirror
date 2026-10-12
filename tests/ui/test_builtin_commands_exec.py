"""Test builtin commands execution."""

from typing import Any

import pytest

from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import Profile
from sensai.ui.command import CommandContext
from sensai.ui.commands.prefs import inst_execute, prefs_execute


class MockUIHandler:
    async def on_system_message(self, message: Any) -> None:
        pass

    async def on_stream_chunk(self, chunk: str) -> None:
        pass

    async def start_spinner(self, message: str) -> None:
        pass

    async def stop_spinner(self) -> None:
        pass

    async def on_tool_call_request(self, _name: str, _args: dict[str, Any]) -> bool:
        return True

    async def on_tool_call_result(self, name: str, result: Any) -> None:
        pass

    async def on_error(self, error: Exception) -> None:
        pass

    async def prompt_choice(
        self, _title: str, _text: str, choices: list[tuple[str, str]]
    ) -> str | None:
        return choices[0][0] if choices else None

    async def prompt_input(self, _title: str, _text: str) -> str | None:
        return "mock_input"


@pytest.mark.asyncio
async def test_prefs_full(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = Profile(name="test", password="test", id=1, preferences="Pref 0\nPref 1")  # noqa: S106
    ProfileManager.current_profile = profile

    monkeypatch.setattr("sensai.ui.commands.prefs.update_profile_preferences", lambda *args: None)

    ctx = CommandContext(database=None, ui=MockUIHandler(), agent=None, config=None, session=None)  # type: ignore[arg-type]

    # List
    await prefs_execute(ctx, ["list"])
    # Edit
    await prefs_execute(ctx, ["edit", "1", "Edited Pref 1"])
    assert profile.preferences == "Pref 0\nEdited Pref 1"
    # Remove
    await prefs_execute(ctx, ["remove", "0"])
    assert profile.preferences == "Edited Pref 1"
    # Add
    await prefs_execute(ctx, ["add", "New"])
    assert profile.preferences == "Edited Pref 1\nNew"
    # Invalid subcmd
    await prefs_execute(ctx, ["invalid"])
    # Invalid args
    await prefs_execute(ctx, ["edit", "99", "Bad"])
    await prefs_execute(ctx, ["edit", "a", "Bad"])
    await prefs_execute(ctx, ["remove", "99"])
    await prefs_execute(ctx, ["add"])

    # No profile
    ProfileManager.current_profile = None
    await prefs_execute(ctx, ["list"])


@pytest.mark.asyncio
async def test_inst_full(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = Profile(name="test", password="test", id=1, instructions="Inst 0\nInst 1")  # noqa: S106
    ProfileManager.current_profile = profile

    monkeypatch.setattr("sensai.ui.commands.prefs.update_profile_instructions", lambda *args: None)

    ctx = CommandContext(database=None, ui=MockUIHandler(), agent=None, config=None, session=None)  # type: ignore[arg-type]

    # List
    await inst_execute(ctx, ["list"])
    # Edit
    await inst_execute(ctx, ["edit", "1", "Edited Inst 1"])
    assert profile.instructions == "Inst 0\nEdited Inst 1"
    # Remove
    await inst_execute(ctx, ["remove", "0"])
    assert profile.instructions == "Edited Inst 1"
    # Add
    await inst_execute(ctx, ["add", "New"])
    assert profile.instructions == "Edited Inst 1\nNew"
    # Invalid subcmd
    await inst_execute(ctx, ["invalid"])
    # Invalid args
    await inst_execute(ctx, ["edit", "99", "Bad"])
    await inst_execute(ctx, ["edit", "a", "Bad"])
    await inst_execute(ctx, ["remove", "99"])
    await inst_execute(ctx, ["add"])

    # No profile
    ProfileManager.current_profile = None
    await inst_execute(ctx, ["list"])


@pytest.mark.asyncio
async def testhelp_execute() -> None:
    ctx = CommandContext(database=None, ui=MockUIHandler(), agent=None, config=None, session=None)  # type: ignore[arg-type]

    from sensai.ui.commands.help import help_execute  # noqa: PLC0415

    await help_execute(ctx, [])


@pytest.mark.asyncio
async def testlogout_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sensai.ui.commands.auth.clear_credentials", lambda: None)

    ctx = CommandContext(database=None, ui=MockUIHandler(), agent=None, config=None, session=None)  # type: ignore[arg-type]

    from sensai.ui.commands.auth import logout_execute  # noqa: PLC0415

    with pytest.raises(SystemExit):
        await logout_execute(ctx, [])


@pytest.mark.asyncio
async def testexit_execute() -> None:
    ctx = CommandContext(database=None, ui=MockUIHandler(), agent=None, config=None, session=None)  # type: ignore[arg-type]

    from sensai.ui.commands.system import exit_execute  # noqa: PLC0415

    with pytest.raises(SystemExit):
        await exit_execute(ctx, [])
