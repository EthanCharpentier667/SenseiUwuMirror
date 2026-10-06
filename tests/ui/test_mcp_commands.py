"""Tests for interactive MCP connections and resource cleanup."""

import json
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


def mcp_command(name: str, url: str) -> str:
    config = json.dumps({"type": "http", "url": url})
    return f"/mcp add-json {name} '{config}'"


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
    ["/mcp", "/mcp invalid", "/mcp ftp://host", "/mcp https://host extra"],
)
async def test_invalid_arguments_do_not_connect(
    monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    commands, registry, context = setup_commands()
    factory = Mock()
    monkeypatch.setattr("sensai.ui.mcp_commands.SensAIClient", factory)
    await registry.execute(command, context)
    factory.assert_not_called()
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
    monkeypatch.setattr(
        "sensai.ui.mcp_commands.SensAIClient", lambda config: connections[config.url]
    )
    await registry.execute(mcp_command("first", "https://first/mcp"), context)
    await registry.execute(mcp_command("first_again", "https://first/mcp"), context)
    await registry.execute(mcp_command("second", "https://second/mcp"), context)
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
    monkeypatch.setattr(
        "sensai.ui.mcp_commands.SensAIClient", lambda config: connections[config.url]
    )
    await registry.execute(mcp_command("first", "https://first/mcp"), context)
    original_tools = list(commands.agent.tools)
    await registry.execute(mcp_command("second", "https://second/mcp"), context)
    assert commands.agent.tools == original_tools
    assert events == ["open first_tool", "open first_tool", "close first_tool"]
    context.ui.on_error.assert_awaited_once()  # type: ignore[attr-defined]
    await commands.aclose()
    assert events[-1] == "close first_tool"


@pytest.mark.asyncio
async def test_add_json_connects_with_headers_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    commands, registry, context = setup_commands()
    events: list[str] = []
    connection = Connection("remote_tool", events)
    factory = Mock(return_value=connection)
    monkeypatch.setattr("sensai.ui.mcp_commands.SensAIClient", factory)
    command = (
        '/mcp add-json github \'{"type": "http", "url": "https://example.com/mcp", '
        '"headers": {"Authorization": "Bearer test-pat"}}\''
    )
    await registry.execute(command, context)
    assert factory.call_args.args[0].headers == {"Authorization": "Bearer test-pat"}
    assert len(commands.agent.tools) == 2
    context.ui.on_error.assert_not_called()  # type: ignore[attr-defined]
    await registry.execute(command, context)
    context.ui.on_error.assert_awaited_once()  # type: ignore[attr-defined]
    assert events == ["open remote_tool"]
    await commands.aclose()
    assert events == ["open remote_tool", "close remote_tool"]
    assert len(commands.agent.tools) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config",
    [
        "not-json",
        "[]",
        '{"type":"stdio"}',
        '{"type":"http"}',
        '{"type":"http","url":"ftp://host"}',
        '{"type":"http","url":"https://host","headers":[]}',
        '{"type":"http","url":"https://host","headers":{"Authorization":42}}',
        '{"type":"http","url":"https\\://host"}',
    ],
)
async def test_add_json_invalid_config_does_not_connect(monkeypatch, config):
    commands, registry, context = setup_commands()
    factory = Mock()
    monkeypatch.setattr("sensai.ui.mcp_commands.SensAIClient", factory)
    await registry.execute(f"/mcp add-json example '{config}'", context)
    factory.assert_not_called()
    context.ui.on_error.assert_awaited_once()  # type: ignore[attr-defined]
    assert len(commands.agent.tools) == 1
    await commands.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command",
    [
        "/mcp add-json",
        "/mcp add-json github",
        "/mcp add-json github '{broken",
    ],
)
async def test_add_json_invalid_arguments_report_error(monkeypatch, command):
    commands, registry, context = setup_commands()
    factory = Mock()
    monkeypatch.setattr("sensai.ui.mcp_commands.SensAIClient", factory)
    await registry.execute(command, context)
    factory.assert_not_called()
    context.ui.on_error.assert_awaited_once()  # type: ignore[attr-defined]
    await commands.aclose()
