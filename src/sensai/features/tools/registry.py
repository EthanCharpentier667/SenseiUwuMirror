"""Registry of the tools available to SensaiUwu."""

from mcp import Client

from sensai.features.tools.web_fetch import WebFetch

from .bash import BashJobTool, BashTool
from .browser.browser_click import BrowserClick
from .browser.browser_navigate import BrowserNavigate
from .browser.browser_screenshot import BrowserScreenshot
from .browser.browser_snapshot import BrowserSnapshot
from .browser.browser_type import BrowserType
from .fileaccess.fileread import FileRead
from .fileaccess.filewrite import FileWrite
from .mcp.mcp_tools import MCPTools
from .sandbox.sandboxed_code import SandboxedCode
from .screenshot.screenshot import Screenshot
from .temperature_example import TempToolExample
from .tool import Tool
from .web_search import WebSearch


def get_tools() -> list[Tool]:
    """Create tools that can be passed to the language model.

    Returns:
        list[Tool]: Instantiated tools ready to be defined and executed.
    """
    return [
        WebSearch(),
        TempToolExample(),
        WebFetch(),
        SandboxedCode(),
        Screenshot(),
        FileRead(),
        FileWrite(),
        BashTool(),
        BashJobTool(),
        BrowserNavigate(),
        BrowserSnapshot(),
        BrowserClick(),
        BrowserType(),
        BrowserScreenshot(),
    ]


async def get_mcp_tools(client: Client, server: str | None = None) -> list[Tool]:
    """Create MCP tools that can be passed to the language model.

    Args:
        client (Client): The connected MCP client.
        server (str | None): The name the server was connected under, used to group its
            tools as ``mcp:<server>``. Default is None, which groups them as ``mcp``.

    Returns:
        list[Tool]: Instantiated tools ready to be defined and executed.
    """
    result = await client.list_tools()
    group = f"mcp:{server}" if server else "mcp"
    return [MCPTools(client, definition, group=group) for definition in result.tools]
