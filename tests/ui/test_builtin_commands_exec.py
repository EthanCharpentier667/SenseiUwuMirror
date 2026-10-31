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
    async def on_prompt(self, payload: dict[str, Any]) -> None:
        pass

    async def on_context_warning(self, used: int, limit: int) -> None:
        pass

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

    from sensai.ui.command import CommandRegistry  # noqa: PLC0415
    from sensai.ui.commands import setup_builtin_commands  # noqa: PLC0415
    from sensai.ui.commands.help import make_help_execute  # noqa: PLC0415

    registry = CommandRegistry()
    setup_builtin_commands(registry)
    ui = _CustomUI(inputs=[], choices=[])
    ctx.ui = ui

    await make_help_execute(registry)(ctx, [])

    commands = [str(cell) for cell in ui.messages[-1].columns[0].cells]
    assert "/persona [list | switch]" in commands
    assert "/settings" in commands


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

    async def on_prompt(self, payload: dict[str, Any]) -> None:
        pass

    async def on_context_warning(self, used: int, limit: int) -> None:
        pass

    async def on_system_message(self, message: Any) -> None:
        self.messages.append(message)


class _FakeAgent:
    def __init__(self, client: "OllamaClient") -> None:
        self.client = client
        self.trust_level = "none"
        self.model = "llama3.2"
        self.max_turns = 10
        self.tools: list[Any] = []

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
        "sensai.data.profile.profile.update_profile_settings",
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


def _settings_context(
    ui: Any, args: list[str] | None = None, token: str | None = None
) -> tuple[CommandContext, Any]:
    from sensai.client import OllamaClient  # noqa: PLC0415
    from sensai.config import Config  # noqa: PLC0415

    config = Config()
    config.parse_args(args or [])
    client = OllamaClient(base_url="http://host-a/api/chat", token=token, timeout=10.0)
    agent = _FakeAgent(client)
    agent.model = config.model
    agent.trust_level = config.trust_level
    agent.max_turns = config.max_steps
    ctx = CommandContext(database=None, ui=ui, agent=agent, config=config, session=None)  # type: ignore[arg-type]
    return ctx, agent


@pytest.mark.asyncio
async def test_settings_compression_threshold_rejects_invalid_values() -> None:
    from sensai.ui.commands.settings import _handle_comp_setting  # noqa: PLC0415

    ui = _CustomUI(inputs=["0", "abc", "5000"], choices=[])
    ctx, _ = _settings_context(ui)
    settings: dict[str, Any] = {}

    await _handle_comp_setting(settings, ctx)
    await _handle_comp_setting(settings, ctx)
    assert settings == {}
    assert "positive integer" in str(ui.messages[-1])
    await _handle_comp_setting(settings, ctx)
    assert settings == {"compression_threshold": 5000}
    assert ctx.config.compression_threshold == 5000


@pytest.mark.asyncio
async def test_settings_url_validates_and_protects_the_token() -> None:
    from sensai.ui.commands.settings import _handle_url_setting  # noqa: PLC0415

    ui = _CustomUI(
        inputs=["not a url", "http://host-a:80", "https://host-b"],
        choices=["drop"],
    )
    ctx, agent = _settings_context(ui, token="secret")  # noqa: S106
    settings: dict[str, Any] = {}

    await _handle_url_setting(settings, ctx)
    assert settings == {}
    assert "Invalid URL" in str(ui.messages[-1])

    # Same host on another port keeps the token; another host only if the user says so.
    await _handle_url_setting(settings, ctx)
    assert agent.client.token == "secret"  # noqa: S105
    await _handle_url_setting(settings, ctx)
    assert settings == {"url": "https://host-b/api/chat", "send_token": False}
    assert agent.client.base_url == "https://host-b/api/chat"
    assert agent.client.token is None


@pytest.mark.asyncio
async def test_settings_url_keeps_the_token_on_the_same_host() -> None:
    from sensai.ui.commands.settings import _handle_url_setting  # noqa: PLC0415

    ui = _CustomUI(inputs=["http://host-a/"], choices=[])
    ctx, agent = _settings_context(ui, token="secret")  # noqa: S106
    settings: dict[str, Any] = {}

    await _handle_url_setting(settings, ctx)

    assert settings == {"url": "http://host-a/api/chat", "send_token": True}
    assert agent.client.token == "secret"  # noqa: S105


@pytest.mark.asyncio
async def test_settings_timeout_and_max_steps() -> None:
    from sensai.ui.commands.settings import (  # noqa: PLC0415
        _handle_max_steps_setting,
        _handle_timeout_setting,
    )

    ui = _CustomUI(inputs=["-1", "45", "default", "0", "3", "default"], choices=[])
    ctx, agent = _settings_context(ui, args=["--timeout", "20", "--max-steps", "7"])
    settings: dict[str, Any] = {}

    await _handle_timeout_setting(settings, ctx)
    assert "Invalid timeout" in str(ui.messages[-1])
    await _handle_timeout_setting(settings, ctx)
    assert settings == {"timeout": 45.0}
    assert agent.client.timeout == 45.0
    await _handle_timeout_setting(settings, ctx)
    assert settings == {}
    assert agent.client.timeout == 20.0

    await _handle_max_steps_setting(settings, ctx)
    assert "Invalid max steps" in str(ui.messages[-1])
    await _handle_max_steps_setting(settings, ctx)
    assert settings == {"max_steps": 3}
    assert agent.max_turns == 3
    await _handle_max_steps_setting(settings, ctx)
    assert settings == {}
    assert agent.max_turns == 7


@pytest.mark.asyncio
async def test_settings_num_ctx_default_restores_the_command_line_value() -> None:
    from sensai.ui.commands.settings import _handle_num_ctx_setting  # noqa: PLC0415

    ui = _CustomUI(inputs=["4096", "default"], choices=[])
    ctx, agent = _settings_context(ui, args=["--num-ctx", "2048"])
    settings: dict[str, Any] = {}

    await _handle_num_ctx_setting(settings, ctx)
    await _handle_num_ctx_setting(settings, ctx)

    assert agent.num_ctx == 2048
    assert ctx.config.num_ctx == 2048


@pytest.mark.asyncio
async def test_settings_menu_saves_only_real_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    from sensai.ui.commands.settings import settings_execute  # noqa: PLC0415

    profile = Profile(name="test", password="test", id=1, settings='{"model": "m"}')  # noqa: S106
    ProfileManager.current_profile = profile
    saved: list[str] = []
    monkeypatch.setattr(
        "sensai.data.profile.profile.update_profile_settings",
        lambda _db, _pid, s: saved.append(s),
    )
    ui = _CustomUI(inputs=[], choices=["tools", "exit"])
    ctx, _ = _settings_context(ui)

    await settings_execute(ctx, [])

    assert saved == []
    assert ui.messages == ["No tools available."]

    ui = _CustomUI(inputs=[], choices=["trust", "partial", "exit"])
    ctx.ui = ui
    await settings_execute(ctx, [])
    assert json.loads(saved[-1]) == {"model": "m", "trust_level": "partial"}
    assert profile.settings == saved[-1]
    assert "Settings saved" in str(ui.messages[-1])


@pytest.mark.asyncio
async def test_settings_features_leave_command_line_overrides_out() -> None:
    from unittest.mock import AsyncMock, Mock  # noqa: PLC0415

    from sensai.features.features import FEATURES, RAG, REACT  # noqa: PLC0415
    from sensai.ui.commands.settings import _handle_features_setting  # noqa: PLC0415

    ui = Mock()
    ctx, _ = _settings_context(ui, args=["--disable", "rag"])
    ui.prompt_checklist = AsyncMock(
        return_value=("ok", [name for name in FEATURES if name not in {RAG, REACT}])
    )
    settings: dict[str, Any] = {}

    await _handle_features_setting(settings, ctx)

    assert ctx.config.features.disabled == {RAG, REACT}
    assert settings == {"disabled_features": [REACT]}


def test_profile_settings_never_beat_explicit_flags() -> None:
    from sensai import _apply_profile_settings  # noqa: PLC0415

    saved = json.dumps(
        {
            "model": "saved-model",
            "url": "http://saved/api/chat",
            "send_token": False,
            "trust_level": "total",
            "compression_threshold": 99,
            "max_steps": 2,
            "timeout": 5.0,
            "disabled_features": ["rag", "teleport"],
            "disabled_tools": ["bash_tool"],
        }
    )
    ui = _CustomUI(inputs=[], choices=[])
    ctx, agent = _settings_context(
        ui,
        args=["--model", "cli-model", "--trust", "partial", "--enable-tool", "bash_tool"],
        token="secret",  # noqa: S106
    )

    _apply_profile_settings(ctx.config, cast("Agent", agent), agent.client, saved)

    assert agent.model == "cli-model"
    assert agent.trust_level == "partial"
    assert agent.client.base_url == "http://saved/api/chat"
    assert agent.client.token is None
    assert ctx.config.compression_threshold == 99
    assert agent.max_turns == 2
    assert agent.client.timeout == 5.0
    assert ctx.config.features.disabled == {"rag"}
    assert ctx.config.features.disabled_tools == set()


def test_profile_settings_ignore_an_unknown_trust_level() -> None:
    from sensai import _apply_profile_settings  # noqa: PLC0415

    ui = _CustomUI(inputs=[], choices=[])
    ctx, agent = _settings_context(ui)

    _apply_profile_settings(ctx.config, cast("Agent", agent), agent.client, '{"trust_level": "x"}')
    _apply_profile_settings(ctx.config, cast("Agent", agent), agent.client, "[1]")
    _apply_profile_settings(ctx.config, cast("Agent", agent), agent.client, "{bad")

    assert agent.trust_level == "none"


@pytest.mark.asyncio
async def test_model_accepts_another_model_with_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    from sensai.ui.commands.model import OTHER, model_execute  # noqa: PLC0415

    profile = Profile(name="test", password="test", id=1, settings=None)  # noqa: S106
    ProfileManager.current_profile = profile
    monkeypatch.setattr("sensai.data.profile.profile.update_profile_settings", lambda *_: None)
    ui = _CustomUI(inputs=["mistral:7b"], choices=[OTHER])
    ctx, agent = _settings_context(ui)

    await model_execute(ctx, [])

    assert agent.model == "mistral:7b"
    assert json.loads(str(profile.settings)) == {"model": "mistral:7b"}
    assert "not in the known models" in str(ui.messages[0])
    assert "Model updated" in str(ui.messages[-1])
