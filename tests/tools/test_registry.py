"""Tests for the tool registry."""

from unittest.mock import AsyncMock, Mock

import pytest
from mcp import Client
from mcp.types import CallToolResult, ListToolsResult, TextContent
from mcp.types import Tool as MCPToolDefinition

from sensai.features.tools.bash import BashJobTool, BashTool
from sensai.features.tools.fileaccess.fileread import FileRead
from sensai.features.tools.fileaccess.filewrite import FileWrite
from sensai.features.tools.registry import get_mcp_tools, get_tools
from sensai.features.tools.sandbox.sandboxed_code import SandboxedCode
from sensai.features.tools.screenshot.screenshot import Screenshot
from sensai.features.tools.temperature_example import TempToolExample
from sensai.features.tools.web_search import WebSearch


def test_get_tools_returns_tool_instances() -> None:
    tools = get_tools()

    assert len(tools) == 9
    assert isinstance(tools[0], WebSearch)
    assert isinstance(tools[1], TempToolExample)
    assert isinstance(tools[3], SandboxedCode)
    assert isinstance(tools[4], Screenshot)
    assert isinstance(tools[5], FileRead)
    assert isinstance(tools[6], FileWrite)
    assert isinstance(tools[7], BashTool)
    assert isinstance(tools[8], BashJobTool)


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

    assert len(tools) == 10
    assert len(remote_tools) == 1
    client.call_tool.assert_not_awaited()
    adapter = remote_tools[0]
    assert adapter.define()["function"]["name"] == "add"
    assert adapter.define()["function"]["parameters"] == definition.input_schema
    output = await adapter.execute(a=2, b=3)
    assert output == result.model_dump(mode="json", exclude_none=True)
    client.list_tools.assert_awaited_once_with()
    client.call_tool.assert_awaited_once_with("add", {"a": 2, "b": 3})
