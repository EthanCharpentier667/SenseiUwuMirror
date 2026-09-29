##
## EPITECH PROJECT, 2026
## SenseiUwuMirror
## File description:
## MCPTools
##


"""Adapt MCP server tools to the Sensai tool interface."""

from typing import Any

from mcp import Client
from mcp.types import Tool as MCPToolDefinition

from sensai.tools.tool import Tool


class MCPTools(Tool):
    """MCP tools implementation."""

    def __init__(self, client: Client, definition: MCPToolDefinition) -> None:
        """Initialize the MCP tools definition."""
        super().__init__(
            name=definition.name,
            description=definition.description or "",
            tool_type="function",
            parameters=definition.input_schema,
        )
        self.client = client

    async def execute(self, *_args: Any, **kwargs: Any) -> dict[str, Any]:
        """Execute the MCP tool's functionality.

        Args:
            *_args: Unused positional arguments.
            **kwargs: Keyword arguments for the tool's execution.

        Returns:
            dict[str, Any]: The result of the MCP tool's execution.
        """
        result = await self.client.call_tool(self.name, kwargs)
        return result.model_dump(mode="json", exclude_none=True)
