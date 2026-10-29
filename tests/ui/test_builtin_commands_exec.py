"""Test builtin commands execution."""

import json
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from sensai.agent import Agent
    from sensai.client import OllamaClient

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

    async def on_stream_end(self) -> None:
        pass

    async def start_spinner(self, message: str) -> None:
        pass

    async def stop_spinner(self) -> None:
        pass

    async def on_tool_call_request(self, _name: str, _args: dict[str, Any]) -> bool:
        return True

    async def on_tool_call_result(
        self, name: str, result: Any, *, show_output: bool = False
    ) -> None:
        pass

    async def render_output(self, content: Any, *, title: str = "Output") -> None:
        pass

    async def on_error(self, error: Exception | str, *, title: str = "Error") -> None:
        pass

    async def on_thinking_chunk(self, chunk: str) -> None:
        pass

    async def prompt_choice(
        self, _title: str, _text: str, choices: list[tuple[str, str]]
    ) -> str | None:
        return choices[0][0] if choices else None

    async def prompt_input(self, _title: str, _text: str) -> str | None:
        return "mock_input"

    async def prompt_checklist(
        self,
        _title: str,
        _text: str,
        _choices: list[tuple[str, str]],
        checked: list[str],
        *,
        extra: str | None = None,  # noqa: ARG002
    ) -> tuple[str, list[str]] | None:
        return ("ok", checked)


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


class _CustomUI(MockUIHandler):
    def __init__(self, inputs: list[str | None], choices: list[str | None]) -> None:
        self.inputs = list(inputs)
        self.choices = list(choices)
        self.messages: list[Any] = []

    async def prompt_input(self, *_args: Any, **_kwargs: Any) -> str | None:
        return self.inputs.pop(0) if self.inputs else None

    async def on_thinking_chunk(self, chunk: str) -> None:
        pass

    async def prompt_choice(self, *_args: Any, **_kwargs: Any) -> str | None:
        return self.choices.pop(0) if self.choices else None

    async def on_system_message(self, message: Any) -> None:
        self.messages.append(message)


class _FakeAgent:
    def __init__(self, client: "OllamaClient") -> None:
        self.client = client
        self.trust_level = "none"
        self.model = "llama3.2"

    @property
    def temperature(self) -> float | None:
        return self.client.temperature

    @temperature.setter
    def temperature(self, val: float | None) -> None:
        self.client.temperature = val

    @property
    def top_p(self) -> float | None:
        return self.client.top_p

    @top_p.setter
    def top_p(self, val: float | None) -> None:
        self.client.top_p = val

    @property
    def num_ctx(self) -> int | None:
        return self.client.num_ctx

    @num_ctx.setter
    def num_ctx(self, val: int | None) -> None:
        self.client.num_ctx = val


@pytest.mark.asyncio
async def test_settings_generation_handlers() -> None:
    from sensai.client import OllamaClient  # noqa: PLC0415
    from sensai.config import Config  # noqa: PLC0415
    from sensai.ui.commands.settings import (  # noqa: PLC0415
        _handle_num_ctx_setting,
        _handle_temperature_setting,
        _handle_top_p_setting,
    )

    config = Config()
    config.parse_args([])
    client = OllamaClient(base_url="http://test", token=None, timeout=10.0)
    agent = _FakeAgent(client)

    # Temperature
    ui = _CustomUI(inputs=["0.7", "-0.1", "bad", "default", None], choices=[])
    ctx = CommandContext(database=None, ui=ui, agent=agent, config=config, session=None)  # type: ignore[arg-type]
    settings: dict[str, Any] = {}

    await _handle_temperature_setting(settings, ctx)
    assert settings["temperature"] == 0.7
    await _handle_temperature_setting(settings, ctx)
    assert "non-negative" in str(ui.messages[-1])
    await _handle_temperature_setting(settings, ctx)
    assert "Invalid temperature format" in str(ui.messages[-1])
    await _handle_temperature_setting(settings, ctx)
    assert "temperature" not in settings
    await _handle_temperature_setting(settings, ctx)

    # Top P
    ui = _CustomUI(inputs=["0.85", "1.5", "bad", "default", None], choices=[])
    ctx.ui = ui
    await _handle_top_p_setting(settings, ctx)
    assert settings["top_p"] == 0.85
    await _handle_top_p_setting(settings, ctx)
    assert "between 0.0 and 1.0" in str(ui.messages[-1])
    await _handle_top_p_setting(settings, ctx)
    assert "Invalid Top P format" in str(ui.messages[-1])
    await _handle_top_p_setting(settings, ctx)
    assert "top_p" not in settings
    await _handle_top_p_setting(settings, ctx)

    # Num Ctx
    ui = _CustomUI(inputs=["8192", "-50", "bad", "default", None], choices=[])
    ctx.ui = ui
    await _handle_num_ctx_setting(settings, ctx)
    assert settings["num_ctx"] == 8192
    await _handle_num_ctx_setting(settings, ctx)
    assert "positive integer" in str(ui.messages[-1])
    await _handle_num_ctx_setting(settings, ctx)
    assert "positive integer" in str(ui.messages[-1])
    await _handle_num_ctx_setting(settings, ctx)
    assert "num_ctx" not in settings
    await _handle_num_ctx_setting(settings, ctx)


@pytest.mark.asyncio
async def test_settings_menu_and_profile_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    from sensai import _apply_profile_settings  # noqa: PLC0415
    from sensai.client import OllamaClient  # noqa: PLC0415
    from sensai.config import Config  # noqa: PLC0415
    from sensai.ui.commands.settings import settings_execute  # noqa: PLC0415

    profile = Profile(name="test", password="test", id=1, settings="{}")  # noqa: S106
    ProfileManager.current_profile = profile
    saved: list[str] = []
    monkeypatch.setattr(
        "sensai.ui.commands.settings.update_profile_settings",
        lambda _db, _pid, s: saved.append(s),
    )

    client = OllamaClient(base_url="http://test", token=None, timeout=10.0)
    agent = _FakeAgent(client)
    config = Config()
    config.parse_args([])

    ui = _CustomUI(
        inputs=["0.5", "0.9", "4096"],
        choices=["temperature", "top_p", "num_ctx", "exit"],
    )
    ctx = CommandContext(database=None, ui=ui, agent=agent, config=config, session=None)  # type: ignore[arg-type]
    await settings_execute(ctx, [])
    assert saved
    saved_dict = json.loads(saved[-1])
    assert saved_dict["temperature"] == 0.5
    assert saved_dict["top_p"] == 0.9
    assert saved_dict["num_ctx"] == 4096

    # Restore in new client
    client2 = OllamaClient(base_url="http://test", token=None, timeout=10.0)
    agent2 = _FakeAgent(client2)
    config2 = Config()
    config2.parse_args([])
    _apply_profile_settings(config2, cast("Agent", agent2), client2, saved[-1])
    assert client2.temperature == 0.5
    assert client2.top_p == 0.9
    assert client2.num_ctx == 4096

    # Verify explicit CLI flags take precedence over saved profile settings
    client3 = OllamaClient(
        base_url="http://test",
        token=None,
        timeout=10.0,
        temperature=0.2,
        top_p=0.4,
        num_ctx=2048,
    )
    agent3 = _FakeAgent(client3)
    config3 = Config()
    config3.parse_args(["--temperature", "0.2", "--top-p", "0.4", "--num-ctx", "2048"])
    _apply_profile_settings(config3, cast("Agent", agent3), client3, saved[-1])
    assert client3.temperature == 0.2
    assert client3.top_p == 0.4
    assert client3.num_ctx == 2048


@pytest.mark.asyncio
async def test_settings_features_checklist() -> None:
    from unittest.mock import AsyncMock, Mock  # noqa: PLC0415

    from sensai.config import Config  # noqa: PLC0415
    from sensai.features.features import FEATURES, MCP, TOOLS  # noqa: PLC0415
    from sensai.ui.commands.settings import _handle_features_setting  # noqa: PLC0415

    config = Config()
    config.parse_args([])
    features = config.features
    features.set(MCP, enabled=False)
    ui = Mock()
    ui.prompt_checklist = AsyncMock(return_value=None)
    ctx = CommandContext(database=None, ui=ui, agent=None, config=config, session=None)  # type: ignore[arg-type]
    settings: dict[str, Any] = {}

    # Cancel changes nothing.
    await _handle_features_setting(settings, ctx)
    kwargs = ui.prompt_checklist.call_args.kwargs
    assert [name for name, _ in kwargs["choices"]] == list(FEATURES)
    assert kwargs["checked"] == [name for name in FEATURES if name != MCP]
    assert features.disabled == {MCP}
    assert settings == {}

    # Unticked features are disabled, ticked ones enabled.
    ui.prompt_checklist.return_value = ("ok", [name for name in FEATURES if name != TOOLS])
    await _handle_features_setting(settings, ctx)
    assert features.disabled == {TOOLS}
    assert settings == {"disabled_features": [TOOLS]}
