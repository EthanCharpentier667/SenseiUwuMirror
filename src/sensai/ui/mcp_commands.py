"""CLI commands for connecting MCP servers during a conversation."""

from contextlib import AsyncExitStack
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from sensai.agent import Agent
from sensai.mcp.github_mcp import GITHUB_MCP_HOST, GitHubMCP
from sensai.mcp.sensai_client import SensAIClient
from sensai.tools.registry import get_mcp_tools
from sensai.ui.command import Command, CommandContext, CommandRegistry

if TYPE_CHECKING:
    from sensai.tools.tool import Tool


class MCPCommands:
    """Keep MCP connections alive until the CLI exits."""

    def __init__(self, agent: Agent) -> None:
        """Track connections and the tools added to the agent."""
        self.agent = agent
        self._stack = AsyncExitStack()
        self._servers: set[str] = set()
        self._tools: list[Tool] = []

    def register(self, registry: CommandRegistry) -> None:
        """Register the public-server and authenticated GitHub commands."""
        registry.register(Command("/mcp", "Connect to an MCP server: /mcp <url>.", self._public))
        registry.register(Command("/mcp-github", "Connect to GitHub MCP.", self._github))

    async def _public(self, context: CommandContext, args: list[str]) -> None:
        if len(args) != 1:
            raise ValueError("Usage: /mcp <url>")
        url = args[0]
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("The MCP URL must be an absolute HTTP or HTTPS URL.")
        await self._connect(context, url, SensAIClient(url))

    async def _github(self, context: CommandContext, args: list[str]) -> None:
        if args:
            raise ValueError("Usage: /mcp-github (set GITHUB_MCP_TOKEN in the environment)")
        await self._connect(context, GITHUB_MCP_HOST, GitHubMCP())

    async def _connect(self, context: CommandContext, url: str, connection: SensAIClient) -> None:
        """Discover tools before adding a successfully opened connection."""
        if url in self._servers:
            await context.ui.on_system_message("This MCP server is already connected.")
            return
        async with AsyncExitStack() as pending:
            client = await pending.enter_async_context(connection.activate())
            tools = await get_mcp_tools(client)
            names = [tool.name for tool in tools]
            existing = {tool.name for tool in self.agent.tools}
            if len(names) != len(set(names)) or existing.intersection(names):
                raise ValueError(
                    "MCP tool names conflict with tools already available to the agent."
                )
            self._stack.push_async_callback(pending.pop_all().aclose)
        self.agent.tools.extend(tools)
        self._tools.extend(tools)
        self._servers.add(url)
        await context.ui.on_system_message(f"MCP connected: {len(tools)} tool(s) added.")

    async def aclose(self) -> None:
        """Remove remote tools and close connections in reverse order."""
        remote_ids = {id(tool) for tool in self._tools}
        self.agent.tools[:] = [tool for tool in self.agent.tools if id(tool) not in remote_ids]
        self._tools.clear()
        self._servers.clear()
        await self._stack.aclose()
