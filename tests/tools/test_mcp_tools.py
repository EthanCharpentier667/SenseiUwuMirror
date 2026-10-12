"""Tests for generic MCP tool execution."""

from unittest.mock import AsyncMock, Mock

import pytest
from mcp import Client
from mcp.types import CallToolResult, TextContent
from mcp.types import Tool as MCPToolDefinition

from sensai.tools.mcp_tools import MCPTools


@pytest.mark.asyncio
async def test_mcp_tool_decodes_schema_typed_json_arguments() -> None:
    """Array and object arguments are decoded for any MCP tool name."""
    definition = MCPToolDefinition(
        name="filter_records",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "fields": {"type": "array", "items": {"type": "string"}},
                "filters": {"type": "object"},
            },
        },
    )
    result = CallToolResult(content=[TextContent(type="text", text="ok")])
    client = Mock(spec=Client)
    client.call_tool = AsyncMock(return_value=result)
    tool = MCPTools(client, definition)

    output = await tool.execute(
        query='["literal query"]',
        fields='["title", "url"]',
        filters='{"state": "open"}',
    )

    client.call_tool.assert_awaited_once_with(
        "filter_records",
        {
            "query": '["literal query"]',
            "fields": ["title", "url"],
            "filters": {"state": "open"},
        },
    )
    assert output == result.model_dump(mode="json", exclude_none=True)


@pytest.mark.asyncio
async def test_mcp_tool_forwards_github_fields_without_a_name_specific_rule() -> None:
    """The generic adapter only converts values requested by the schema."""
    definition = MCPToolDefinition(
        name="list_pull_requests",
        input_schema={
            "type": "object",
            "properties": {"fields": {"type": "array", "items": {"type": "string"}}},
        },
    )
    client = Mock(spec=Client)
    client.call_tool = AsyncMock(return_value=CallToolResult(content=[]))

    tool = MCPTools(client, definition)
    await tool.execute(fields='["title", "html_url"]')

    client.call_tool.assert_awaited_once_with(
        "list_pull_requests", {"fields": ["title", "html_url"]}
    )
