"""CLI commands for connecting MCP servers during a conversation."""

from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

from sensai.agent import Agent
from sensai.mcp.config import MCPServerConfig, validate_http_url
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
        self._names: set[str] = set()
        self._tools: list[Tool] = []

    def register(self, registry: CommandRegistry) -> None:
        """Register the MCP server connection command."""
        registry.register(
            Command(
                "/mcp",
                "Connect: /mcp <url> or /mcp add-json <name> '<json>'.",
                self._public,
                subcommands=["add-json"],
            )
        )

    async def _public(self, context: CommandContext, args: list[str]) -> None:
        if args and args[0] == "add-json":
            await self._add_json(context, args[1:])
            return
        if len(args) != 1:
            raise ValueError("Usage: /mcp <url>")
        url = validate_http_url(args[0])
        await self._connect(context, url, SensAIClient(url))

    async def _add_json(self, context: CommandContext, args: list[str]) -> None:
        """Connect a named server using validated JSON settings."""
        if len(args) != 2 or not args[0].strip():  # noqa: PLR2004
            raise ValueError("Usage: /mcp add-json <name> '<json>'")
        name, raw_json = args
        config = MCPServerConfig.from_json(raw_json)
        if name in self._names:
            raise ValueError("This MCP server name is already connected.")
        await self._connect(
            context, config.url, SensAIClient(config.url), headers=config.headers, name=name
        )

    async def _connect(
        self,
        context: CommandContext,
        url: str,
        connection: SensAIClient,
        *,
        headers: dict[str, str] | None = None,
        name: str | None = None,
    ) -> None:
        """Discover tools before adding a successfully opened connection."""
        if url in self._servers:
            await context.ui.on_system_message("This MCP server is already connected.")
            return
        async with AsyncExitStack() as pending:
            activation = (
                connection.activate()
                if headers is not None
                else connection.activate_json(headers=headers)
            )
            client = await pending.enter_async_context(activation)
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
        if name is not None:
            self._names.add(name)
        await context.ui.on_system_message(f"MCP connected: {len(tools)} tool(s) added.")

    async def aclose(self) -> None:
        """Remove remote tools and close connections in reverse order."""
        remote_ids = {id(tool) for tool in self._tools}
        self.agent.tools[:] = [tool for tool in self.agent.tools if id(tool) not in remote_ids]
        self._tools.clear()
        self._servers.clear()
        self._names.clear()
        await self._stack.aclose()
