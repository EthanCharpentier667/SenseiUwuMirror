"""Tests for the /tools command."""

import json
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from mcp import Client
from mcp.types import Tool as MCPToolDefinition
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from sensai.agent import Agent
from sensai.client import OllamaClient
from sensai.config import Config
from sensai.data.database.database import Database
from sensai.data.profile.manager import ProfileManager
from sensai.data.session.session import Session
from sensai.features.features import MCP, TOOLS
from sensai.features.tools.bash import BashJobTool, BashTool
from sensai.features.tools.browser.browser_click import BrowserClick
from sensai.features.tools.browser.browser_snapshot import BrowserSnapshot
from sensai.features.tools.mcp.mcp_tools import MCPTools
from sensai.features.tools.temperature_example import TempToolExample
from sensai.features.tools.tool import Tool
from sensai.ui.command import CommandContext
from sensai.ui.commands import tool as tool_command
from sensai.ui.commands.tool import USAGE, ToolNameCompleter, tool_execute
from sensai.ui.protocol import AsyncUIHandler


def make_context(
    monkeypatch: pytest.MonkeyPatch, tools: list[Tool] | None = None
) -> tuple[CommandContext, Any]:
    monkeypatch.setattr(ProfileManager, "current_profile", None)
    config = Config()
    config.parse_args([])
    agent = Agent(
        tools=tools if tools is not None else [TempToolExample()],
        client=Mock(spec=OllamaClient),
        features=config.features,
    )
    ui = Mock(spec=AsyncUIHandler)
    ui.on_system_message = AsyncMock()
    ui.prompt_checklist = AsyncMock(return_value=None)
    ui.prompt_choice = AsyncMock(return_value=None)
    context = CommandContext(
        database=Mock(spec=Database),
        ui=ui,
        agent=agent,
        config=config,
        session=Mock(spec=Session),
    )
    return context, ui


def mixed_tools() -> list[Tool]:
    definition = MCPToolDefinition(name="create_issue", input_schema={"type": "object"})
    return [
        BrowserSnapshot(),
        BrowserClick(),
        BashTool(),
        BashJobTool(),
        MCPTools(Mock(spec=Client), definition, group="mcp:github"),
    ]


def available(context: CommandContext) -> set[str]:
    return {tool.name for tool in context.agent.available_tools()}


def messages(ui: Any) -> list[Any]:
    return [call.args[0] for call in ui.on_system_message.call_args_list]


@pytest.mark.asyncio
async def test_tool_disable_then_enable_a_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    context, _ = make_context(monkeypatch)
    name = TempToolExample().name

    await tool_execute(context, ["disable", name])
    assert context.agent.available_tools() == []

    await tool_execute(context, ["enable", name])
    assert [tool.name for tool in context.agent.available_tools()] == [name]


@pytest.mark.asyncio
async def test_tool_rejects_an_unknown_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    context, ui = make_context(monkeypatch)

    await tool_execute(context, ["disable", "teleport"])

    assert context.config.features.disabled_tools == set()
    assert "Unknown tool or group: teleport" in ui.on_system_message.call_args.args[0]


@pytest.mark.asyncio
async def test_tool_disables_groups_and_tools_and_reports_unknown_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, ui = make_context(monkeypatch, mixed_tools())

    await tool_execute(context, ["disable", "browser", "bash_job", "teleport"])

    assert available(context) == {"bash_tool", "create_issue"}
    assert "browser_snapshot, browser_click, bash_job" in messages(ui)[0]
    assert "Unknown tool or group: teleport" in messages(ui)[1]


@pytest.mark.asyncio
async def test_tool_saves_choices_to_the_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    context, _ = make_context(monkeypatch, mixed_tools())
    profile = Mock(id=1, settings=json.dumps({"trust_level": "partial"}))
    monkeypatch.setattr(ProfileManager, "current_profile", profile)
    saved = Mock()
    monkeypatch.setattr(tool_command, "update_profile_settings", saved)

    await tool_execute(context, ["disable", "bash"])

    settings = json.loads(saved.call_args.args[2])
    assert settings == {
        "trust_level": "partial",
        "disabled_tools": ["bash_job", "bash_tool"],
        "disabled_features": [],
    }
    assert profile.settings == saved.call_args.args[2]


@pytest.mark.asyncio
async def test_tool_list_shows_group_source_safety_and_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, ui = make_context(monkeypatch, mixed_tools())
    context.config.features.set_tool("bash_tool", enabled=False)
    context.config.features.set(MCP, enabled=False)

    await tool_execute(context, ["list"])

    table = messages(ui)[-1]
    rows = list(zip(*(column.cells for column in table.columns), strict=True))
    by_name = {str(row[0]): row for row in rows}
    assert table.row_count == 5
    assert str(by_name["browser_snapshot"][2]) == "built-in"
    assert by_name["browser_snapshot"][3] == "yes"
    assert "on" in by_name["browser_snapshot"][4]
    assert "off (disabled)" in by_name["bash_tool"][4]
    assert str(by_name["create_issue"][2]) == "mcp:github"
    assert "off (mcp feature off)" in by_name["create_issue"][4]


@pytest.mark.asyncio
async def test_tool_list_explains_when_the_tools_feature_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, ui = make_context(monkeypatch, mixed_tools())
    context.config.features.set(TOOLS, enabled=False)

    await tool_execute(context, ["list"])

    assert "tools feature is off" in messages(ui)[0]
    assert "off (tools feature off)" in next(iter(messages(ui)[1].columns[4].cells))


@pytest.mark.asyncio
async def test_tool_shows_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    context, ui = make_context(monkeypatch)

    await tool_execute(context, ["bogus"])
    ui.on_system_message.assert_called_with(USAGE)

    await tool_execute(context, ["enable"])
    ui.on_system_message.assert_called_with(USAGE)


@pytest.mark.asyncio
async def test_tool_dialog_toggles_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    context, ui = make_context(monkeypatch, mixed_tools())
    features = context.config.features
    features.set_tool("bash_job", enabled=False)
    ui.prompt_checklist.return_value = ("ok", ["group:bash", "group:mcp:github"])

    await tool_execute(context, [])

    choices = dict(ui.prompt_checklist.call_args.kwargs["choices"])
    assert choices["group:bash"] == "bash (1/2 on)"
    assert not any(choice.startswith("feature:") for choice in choices)
    assert "group:bash" in ui.prompt_checklist.call_args.kwargs["checked"]
    # Unticked: the browser group. Bash stays partially on, and features are untouched.
    assert features.disabled == set()
    assert available(context) == {"bash_tool", "create_issue"}
    assert "Tool settings saved" in messages(ui)[-1]


@pytest.mark.asyncio
async def test_tool_dialog_fine_tunes_one_group(monkeypatch: pytest.MonkeyPatch) -> None:
    context, ui = make_context(monkeypatch, mixed_tools())
    ticked_groups = ["group:browser", "group:bash"]
    ui.prompt_checklist.side_effect = [("extra", ticked_groups), ("ok", ["browser_snapshot"])]
    ui.prompt_choice.return_value = "browser"

    await tool_execute(context, [])

    assert available(context) == {"browser_snapshot", "bash_tool", "bash_job"}


@pytest.mark.asyncio
async def test_tool_dialog_cancel_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    context, ui = make_context(monkeypatch, mixed_tools())
    saved = Mock()
    monkeypatch.setattr(tool_command, "save_tool_settings", saved)

    await tool_execute(context, [])

    assert len(available(context)) == 5
    saved.assert_not_called()
    ui.on_system_message.assert_not_called()


@pytest.mark.asyncio
async def test_tool_dialog_without_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    context, ui = make_context(monkeypatch, [])

    await tool_execute(context, [])

    ui.prompt_checklist.assert_not_called()
    ui.on_system_message.assert_called_with("No tools available.")


def test_tool_name_completer_suggests_groups_and_tools() -> None:
    agent = Agent(tools=mixed_tools(), client=Mock(spec=OllamaClient))
    completer = ToolNameCompleter(agent)

    def complete(text: str) -> list[str]:
        document = Document(text)
        return [c.text for c in completer.get_completions(document, CompleteEvent())]

    assert complete("/tools disable b") == [
        "browser",
        "bash",
        "browser_snapshot",
        "browser_click",
        "bash_tool",
        "bash_job",
    ]
    assert complete("/tools enable bash bash") == ["bash_tool", "bash_job"]
    assert complete("/tools enable mcp") == ["mcp:github"]
    assert complete("/tools list b") == []
