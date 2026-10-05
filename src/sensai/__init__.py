"""Sensai: LLM chatbot with unlimited functionalities."""

import asyncio
import os
from contextlib import AsyncExitStack

from rich.console import Console

from sensai.config import Config
from sensai.core.setup import (
    get_or_create_session,
    ingest_initial_files,
    setup_ai_engine,
    setup_database,
)
from sensai.embedder import Embedder
from sensai.mcp.github_mcp import GitHubMCP
from sensai.mcp.sensai_client import SensAIClient
from sensai.tools.registry import get_mcp_tools
from sensai.ui.app import CLIApp
from sensai.ui.auth import authenticate_user

# Temporary MCP settings until configuration is available.
USE_MCP_MODE = True
USE_GITHUB_MCP = True
MCP_SERVER_URL = "https://docs.mcp.cloudflare.com/mcp"

__all__ = ["CLIApp", "main"]


async def async_main() -> None:
    """Async entry point for the ``sensai`` console script."""
    config = Config()
    config.parse_args()

    database = setup_database(config)
    client, agent = setup_ai_engine(config)
    embedder = Embedder(client)

    console = Console()
    profile = await authenticate_user(database, console)
    session = get_or_create_session(database, profile)

    await ingest_initial_files(database, embedder, session, config.files, console)

    app = CLIApp(
        agent=agent,
        database=database,
        session=session,
        client=client,
        config=config,
        profile_name=profile.name,
        embedder=embedder,
    )
    async with AsyncExitStack() as stack:
        mcp_client = None
        if USE_MCP_MODE and USE_GITHUB_MCP and os.environ.get("GITHUB_MCP_TOKEN") is not None:
            mcp_client = await stack.enter_async_context(GitHubMCP().activate())
        elif USE_MCP_MODE and MCP_SERVER_URL:
            mcp_client = await stack.enter_async_context(SensAIClient(MCP_SERVER_URL).activate())
        if mcp_client is not None:
            agent.tools.extend(await get_mcp_tools(mcp_client))
        await app.run()


def main() -> None:
    """Entry point for the ``sensai`` console script."""
    asyncio.run(async_main())
