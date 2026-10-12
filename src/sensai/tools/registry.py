"""Registry of the tools available to Sensai."""

from mcp import Client

from sensai.tools.web_fetch import WebFetch

from .mcp_tools import MCPTools
from .temperature_example import TempToolExample
from .tool import Tool
from .web_search import WebSearch


def get_tools() -> list[Tool]:
    """Create tools that can be passed to the language model.

    Returns:
        list[Tool]: Instantiated tools ready to be defined and executed.
    """
    return [WebSearch(), TempToolExample(), WebFetch()]


async def get_mcp_tools(client: Client) -> list[Tool]:
    """Create MCP tools that can be passed to the language model.

    Returns:
        list[Tool]: Instantiated tools ready to be defined and executed.
    """
    result = await client.list_tools()
    return [MCPTools(client, definition) for definition in result.tools]
