"""Test builtin commands execution."""

from typing import Any

import pytest

from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import Profile
from sensai.ui.builtin_commands import _inst_execute, _prefs_execute
from sensai.ui.command import CommandContext


class MockUIHandler:
    async def on_system_message(self, message: Any) -> None:
        pass

    async def on_stream_chunk(self, chunk: str) -> None: pass
    async def on_tool_call_request(self, name: str, args: dict[str, Any]) -> bool: return True
    async def on_tool_call_result(self, name: str, result: Any) -> None: pass
    async def on_error(self, error: Exception) -> None: pass


@pytest.mark.asyncio
async def test_prefs_full(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = Profile(name="test", password="test", id=1, preferences="Pref 0\nPref 1")  # noqa: S106
    ProfileManager.current_profile = profile

    monkeypatch.setattr("sensai.ui.builtin_commands.update_profile_preferences", lambda *args: None)

    ctx = CommandContext(database=None, ui=MockUIHandler())  # type: ignore[arg-type]

    # List
    await _prefs_execute(ctx, ["list"])
    # Edit
    await _prefs_execute(ctx, ["edit", "1", "Edited Pref 1"])
    assert profile.preferences == "Pref 0\nEdited Pref 1"
    # Remove
    await _prefs_execute(ctx, ["remove", "0"])
    assert profile.preferences == "Edited Pref 1"
    # Add
    await _prefs_execute(ctx, ["add", "New"])
    assert profile.preferences == "Edited Pref 1\nNew"
    # Invalid subcmd
    await _prefs_execute(ctx, ["invalid"])
    # Invalid args
    await _prefs_execute(ctx, ["edit", "99", "Bad"])
    await _prefs_execute(ctx, ["edit", "a", "Bad"])
    await _prefs_execute(ctx, ["remove", "99"])
    await _prefs_execute(ctx, ["add"])

    # No profile
    ProfileManager.current_profile = None
    await _prefs_execute(ctx, ["list"])

@pytest.mark.asyncio
async def test_inst_full(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = Profile(name="test", password="test", id=1, instructions="Inst 0\nInst 1")  # noqa: S106
    ProfileManager.current_profile = profile

    monkeypatch.setattr("sensai.ui.builtin_commands.update_profile_instructions", lambda *args: None)

    ctx = CommandContext(database=None, ui=MockUIHandler())  # type: ignore[arg-type]

    # List
    await _inst_execute(ctx, ["list"])
    # Edit
    await _inst_execute(ctx, ["edit", "1", "Edited Inst 1"])
    assert profile.instructions == "Inst 0\nEdited Inst 1"
    # Remove
    await _inst_execute(ctx, ["remove", "0"])
    assert profile.instructions == "Edited Inst 1"
    # Add
    await _inst_execute(ctx, ["add", "New"])
    assert profile.instructions == "Edited Inst 1\nNew"
    # Invalid subcmd
    await _inst_execute(ctx, ["invalid"])
    # Invalid args
    await _inst_execute(ctx, ["edit", "99", "Bad"])
    await _inst_execute(ctx, ["edit", "a", "Bad"])
    await _inst_execute(ctx, ["remove", "99"])
    await _inst_execute(ctx, ["add"])

    # No profile
    ProfileManager.current_profile = None
    await _inst_execute(ctx, ["list"])

@pytest.mark.asyncio
async def test_help_execute() -> None:
    ctx = CommandContext(database=None, ui=MockUIHandler())  # type: ignore[arg-type]

    from sensai.ui.builtin_commands import _help_execute
    await _help_execute(ctx, [])


@pytest.mark.asyncio
async def test_logout_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sensai.ui.builtin_commands.clear_credentials", lambda: None)

    ctx = CommandContext(database=None, ui=MockUIHandler())  # type: ignore[arg-type]

    with pytest.raises(SystemExit):
        from sensai.ui.builtin_commands import _logout_execute
        await _logout_execute(ctx, [])


@pytest.mark.asyncio
async def test_exit_execute() -> None:
    ctx = CommandContext(database=None, ui=MockUIHandler())  # type: ignore[arg-type]

    with pytest.raises(SystemExit):
        from sensai.ui.builtin_commands import _exit_execute
        await _exit_execute(ctx, [])
