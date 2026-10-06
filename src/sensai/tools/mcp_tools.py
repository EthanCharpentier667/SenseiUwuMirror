##
## EPITECH PROJECT, 2026
## SenseiUwuMirror
## File description:
## MCPTools
##


"""Adapt MCP server tools to the Sensai tool interface."""

import json
from collections.abc import Callable
from typing import Any

from mcp import Client
from mcp.types import Tool as MCPToolDefinition

from sensai.tools.tool import Tool


def _decode_json_arguments(arguments: dict[str, Any], properties: dict[str, Any]) -> dict[str, Any]:
    """Decode JSON text only when the MCP schema expects an array or object."""
    decoded = arguments.copy()
    for name, value in arguments.items():
        schema = properties.get(name, {})
        if not isinstance(schema, dict) or not isinstance(value, str):
            continue
        schema_type = schema.get("type")
        if schema_type not in {"array", "object"}:
            continue
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            continue
        if (schema_type == "array" and isinstance(parsed, list)) or (
            schema_type == "object" and isinstance(parsed, dict)
        ):
            decoded[name] = parsed
    return decoded


class MCPTools(Tool):
    """Adapt any MCP tool definition and call it through its connected client."""

    def __init__(
        self,
        client: Client,
        definition: MCPToolDefinition,
        argument_transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        """Initialize the MCP tool and its optional argument policy."""
        super().__init__(
            name=definition.name,
            description=definition.description or "",
            tool_type="function",
            parameters=definition.input_schema,
        )
        self.client = client
        self.argument_transform = argument_transform

    async def execute(self, *_args: Any, **kwargs: Any) -> dict[str, Any]:
        """Execute the MCP tool's functionality.

        Args:
            *_args: Unused positional arguments.
            **kwargs: Keyword arguments for the tool's execution.

        Returns:
            dict[str, Any]: The result of the MCP tool's execution.
        """
        arguments = _decode_json_arguments(kwargs, self.parameters.get("properties", {}))
        if self.argument_transform is not None:
            arguments = self.argument_transform(arguments)
        result = await self.client.call_tool(self.name, arguments)
        return result.model_dump(mode="json", exclude_none=True)
