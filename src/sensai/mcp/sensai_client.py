"""MCP client connection for SensAI."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


class SensAIClient(Client):
    """Client for MCP servers with optional HTTP headers."""

    def __init__(self, server_url: str) -> None:
        """Configure the remote server address."""
        self.server_url = server_url
        super().__init__(server_url)

    @asynccontextmanager
    async def activate(self) -> AsyncGenerator[Client, None]:
        """Activate the MCP client for SensAI."""
        try:
            async with self:
                yield self
        except Exception as e:
            raise RuntimeError(f"Failed to connect to MCP server: {e}") from e

    @asynccontextmanager
    async def activate_json(
        self, *, headers: dict[str, str] | None = None
    ) -> AsyncGenerator[Client, None]:
        """Activate the HTTP transport using headers from a JSON configuration."""
        async with httpx2.AsyncClient(headers=headers or {}) as http_client:
            transport = streamable_http_client(self.server_url, http_client=http_client)
            async with Client(transport) as client:
                yield client
