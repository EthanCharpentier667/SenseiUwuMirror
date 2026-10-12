"""Tests for the tool registry."""

from unittest.mock import AsyncMock, Mock

import pytest
from mcp import Client
from mcp.types import CallToolResult, ListToolsResult, TextContent
from mcp.types import Tool as MCPToolDefinition

from sensai.tools.registry import get_mcp_tools, get_tools
from sensai.tools.temperature_example import TempToolExample
from sensai.tools.web_search import WebSearch


def test_get_tools_returns_tool_instances() -> None:
    tools = get_tools()

    assert len(tools) == 3
    assert isinstance(tools[0], WebSearch)
    assert isinstance(tools[1], TempToolExample)


@pytest.mark.asyncio
async def test_mcp_tools_are_discovered_and_executed_remotely() -> None:

    definition = MCPToolDefinition(
        name="add",
        description="Add two numbers.",
        input_schema={
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
    )
    result = CallToolResult(content=[TextContent(type="text", text="5")])
    client = Mock(spec=Client)
    client.list_tools = AsyncMock(return_value=ListToolsResult(tools=[definition]))
    client.call_tool = AsyncMock(return_value=result)

    remote_tools = await get_mcp_tools(client)
    tools = get_tools() + remote_tools

    assert len(tools) == 4
    assert len(remote_tools) == 1
    client.call_tool.assert_not_awaited()
    adapter = remote_tools[0]
    assert adapter.define()["function"]["name"] == "add"
    assert adapter.define()["function"]["parameters"] == definition.input_schema
    output = await adapter.execute(a=2, b=3)
    assert output == result.model_dump(mode="json", exclude_none=True)
    client.list_tools.assert_awaited_once_with()
    client.call_tool.assert_awaited_once_with("add", {"a": 2, "b": 3})
