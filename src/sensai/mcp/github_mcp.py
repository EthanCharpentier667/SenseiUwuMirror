"""GitHub Model Control Protocol."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from sensai.mcp.sensai_client import SensAIClient

GITHUB_MCP_HOST = "https://api.githubcopilot.com/mcp/"


class GitHubMCP(SensAIClient):
    """Client for the GitHub Model Control Protocol (MCP)."""

    def __init__(self) -> None:
        """Initialize the GitHub MCP client."""
        super().__init__(GITHUB_MCP_HOST)

    @asynccontextmanager
    async def activate(self) -> AsyncGenerator[Client, None]:
        """Connect to an MCP server, using a GitHub token when required."""
        server_url = GITHUB_MCP_HOST
        token = os.environ.get("GITHUB_MCP_TOKEN", None)

        if token is None:
            raise ValueError("GITHUB_MCP_TOKEN is required to connect to the GitHub MCP server.")

        async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as http_client:
            transport = streamable_http_client(server_url, http_client=http_client)
            async with Client(transport) as client:
                yield client
