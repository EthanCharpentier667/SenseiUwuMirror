"""MCP client connection for SensAI."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

GITHUB_MCP_HOST = "https://api.githubcopilot.com/mcp/"


class SensAIClient(Client):
    """Client for an MCP server that does not require authentication."""

    def __init__(self, server_url: str) -> None:
        """Configure the remote server address."""
        super().__init__(server_url)


@asynccontextmanager
async def activate_github_mcp_client() -> AsyncGenerator[Client, None]:
    """Connect to an MCP server, using a GitHub token when required."""
    server_url = GITHUB_MCP_HOST
    token = os.environ.get("GITHUB_MCP_TOKEN", None)

    if token is None:
        raise ValueError("GITHUB_MCP_TOKEN is required to connect to the GitHub MCP server.")

    async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as http_client:
        transport = streamable_http_client(server_url, http_client=http_client)
        async with Client(transport) as client:
            yield client


def activate_mcp_client(server_url: str) -> SensAIClient:
    """Activate the MCP client for SensAI."""
    return SensAIClient(server_url)
