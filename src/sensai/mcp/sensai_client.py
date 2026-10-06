"""MCP client connection for SensAI."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from sensai.mcp.config import MCPServerConfig
from sensai.mcp.oauth import OAuth


class SensAIClient:
    """Client for MCP servers with optional HTTP headers."""

    def __init__(self, config: MCPServerConfig) -> None:
        """Store connection settings parsed from JSON."""
        self.config = config
        self._oauth = OAuth(config.url, config.oauth) if config.oauth is not None else None

    @asynccontextmanager
    async def activate(self) -> AsyncGenerator[Client, None]:
        """Activate the HTTP transport using headers from a JSON configuration."""
        async with httpx2.AsyncClient(auth=self._oauth, headers=self.config.headers) as http_client:
            transport = streamable_http_client(self.config.url, http_client=http_client)
            async with Client(transport) as client:
                yield client
