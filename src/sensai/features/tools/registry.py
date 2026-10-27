"""Registry of the tools available to Sensai."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sensai.features.tools.web_fetch import WebFetch

from .ask_user import AskUserTool
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
from .web_search import WebSearch

if TYPE_CHECKING:
    from mcp import Client

    from sensai.ui.protocol import AsyncUIHandler

    from .tool import Tool


def get_tools(ui_handler: AsyncUIHandler | None = None) -> list[Tool]:
    """Create tools that can be passed to the language model.

    Returns:
        list[Tool]: Instantiated tools ready to be defined and executed.
    """
    tools = [
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
    if ui_handler is not None:
        tools.append(AskUserTool(ui_handler))
    return tools


async def get_mcp_tools(client: Client) -> list[Tool]:
    """Create MCP tools that can be passed to the language model.

    Returns:
        list[Tool]: Instantiated tools ready to be defined and executed.
    """
    result = await client.list_tools()
    return [MCPTools(client, definition) for definition in result.tools]
