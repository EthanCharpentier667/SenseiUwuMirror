"""MCP client connection for SensAI."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from mcp import Client


class SensAIClient(Client):
    """Client for an MCP server that does not require authentication."""

    def __init__(self, server_url: str) -> None:
        """Configure the remote server address."""
        super().__init__(server_url)

    @asynccontextmanager
    async def activate(self) -> AsyncGenerator[Client, None]:
        """Activate the MCP client for SensAI."""
        async with self:
            yield self
