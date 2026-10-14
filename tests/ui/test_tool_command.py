"""Tests for the /tools command."""

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from sensai.agent import Agent
from sensai.client import OllamaClient
from sensai.config import Config
from sensai.data.database.database import Database
from sensai.data.profile.manager import ProfileManager
from sensai.data.session.session import Session
from sensai.features.tools.temperature_example import TempToolExample
from sensai.ui.command import CommandContext
from sensai.ui.commands.tool import USAGE, tool_execute
from sensai.ui.protocol import AsyncUIHandler


def make_context(monkeypatch: pytest.MonkeyPatch) -> tuple[CommandContext, Any]:
    monkeypatch.setattr(ProfileManager, "current_profile", None)
    config = Config()
    config.parse_args([])
    agent = Agent(
        tools=[TempToolExample()], client=Mock(spec=OllamaClient), features=config.features
    )
    ui = Mock(spec=AsyncUIHandler)
    ui.on_system_message = AsyncMock()
    context = CommandContext(
        database=Mock(spec=Database),
        ui=ui,
        agent=agent,
        config=config,
        session=Mock(spec=Session),
    )
    return context, ui


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
    assert "Unknown tool" in ui.on_system_message.call_args.args[0]


@pytest.mark.asyncio
async def test_tool_lists_tools_and_shows_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    context, ui = make_context(monkeypatch)

    await tool_execute(context, [])
    assert ui.on_system_message.call_args.args[0].row_count == 1

    await tool_execute(context, ["bogus"])
    ui.on_system_message.assert_called_with(USAGE)
