"""Tests for interactive MCP connections and resource cleanup."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import anyio
import pytest
from mcp import Client
from mcp.types import Tool as MCPToolDefinition

from sensai.agent import Agent
from sensai.data.database.database import Database
from sensai.tools.temperature_example import TempToolExample
from sensai.ui.command import CommandContext, CommandRegistry
from sensai.ui.mcp_commands import MCPCommands
from sensai.ui.protocol import AsyncUIHandler


class Connection:
    """Simulate MCP task scopes to enforce same-task, reverse-order cleanup."""

    def __init__(self, name: str, events: list[str]) -> None:
        """Prepare a client with one remote tool and lifecycle tracking."""
        self.name = name
        self.events = events
        self.client = AsyncMock(spec=Client)
        self.client.list_tools.return_value = SimpleNamespace(
            tools=[MCPToolDefinition(name=name, input_schema={"type": "object"})]
        )

    @asynccontextmanager
    async def activate(self) -> AsyncIterator[Client]:
        async with anyio.create_task_group():
            self.events.append(f"open {self.name}")
            try:
                yield self.client
            finally:
                self.events.append(f"close {self.name}")


def setup_commands() -> tuple[MCPCommands, CommandRegistry, CommandContext]:
    agent = Mock(spec=Agent, tools=[TempToolExample()])
    commands = MCPCommands(agent)
    registry = CommandRegistry()
    commands.register(registry)
    context = CommandContext(database=Mock(spec=Database), ui=Mock(spec=AsyncUIHandler))
    return commands, registry, context


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command",
    ["/mcp", "/mcp invalid", "/mcp ftp://host", "/mcp https://host extra", "/mcp-github extra"],
)
async def test_invalid_arguments_do_not_connect(
    monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    commands, registry, context = setup_commands()
    factory = Mock()
    monkeypatch.setattr("sensai.ui.mcp_commands.SensAIClient", factory)
    monkeypatch.setattr("sensai.ui.mcp_commands.GitHubMCP", factory)
    await registry.execute(command, context)
    factory.assert_not_called()
    context.ui.on_error.assert_awaited_once()  # type: ignore[attr-defined]
    assert len(commands.agent.tools) == 1
    await commands.aclose()


@pytest.mark.asyncio
async def test_missing_github_token_reports_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_MCP_TOKEN", raising=False)
    commands, registry, context = setup_commands()
    await registry.execute("/mcp-github", context)
    context.ui.on_error.assert_awaited_once()  # type: ignore[attr-defined]
    assert len(commands.agent.tools) == 1
    await commands.aclose()


@pytest.mark.asyncio
async def test_multiple_servers_and_repeated_command(monkeypatch: pytest.MonkeyPatch) -> None:
    commands, registry, context = setup_commands()
    events: list[str] = []
    first = Connection("first_tool", events)
    second = Connection("second_tool", events)
    connections = {"https://first/mcp": first, "https://second/mcp": second}
    monkeypatch.setattr("sensai.ui.mcp_commands.SensAIClient", connections.__getitem__)
    await registry.execute("/mcp https://first/mcp", context)
    await registry.execute("/mcp https://first/mcp", context)
    await registry.execute("/mcp https://second/mcp", context)
    assert len(commands.agent.tools) == 3
    first.client.list_tools.assert_awaited_once()
    assert events == ["open first_tool", "open second_tool"]
    await commands.aclose()
    assert events == [
        "open first_tool",
        "open second_tool",
        "close second_tool",
        "close first_tool",
    ]
    assert len(commands.agent.tools) == 1
    context.ui.on_error.assert_not_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["discovery", "collision"])
async def test_failed_connection_keeps_existing_tools(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    commands, registry, context = setup_commands()
    events: list[str] = []
    first = Connection("first_tool", events)
    second = Connection("first_tool", events)
    if failure == "discovery":
        second.client.list_tools.side_effect = RuntimeError("Discovery failed")
    connections = {"https://first/mcp": first, "https://second/mcp": second}
    monkeypatch.setattr("sensai.ui.mcp_commands.SensAIClient", connections.__getitem__)
    await registry.execute("/mcp https://first/mcp", context)
    original_tools = list(commands.agent.tools)
    await registry.execute("/mcp https://second/mcp", context)
    assert commands.agent.tools == original_tools
    assert events == ["open first_tool", "open first_tool", "close first_tool"]
    context.ui.on_error.assert_awaited_once()  # type: ignore[attr-defined]
    await commands.aclose()
    assert events[-1] == "close first_tool"
