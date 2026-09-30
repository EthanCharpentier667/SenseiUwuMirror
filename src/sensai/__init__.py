"""Sensai: LLM chatbot with unlimited functionalities."""

import asyncio
import os

from .agent import Agent
from .client import OllamaClient
from .config import Config
from .data.database.database import Database
from .data.profile.manager import add_instruction, add_preference, create_new_profile, login
from .data.session.manager import (
    build_messages,
    create_new_session,
    maybe_compress_session,
    update_session,
)
from .data.session.session import Session
from .mcp.sensai_client import activate_github_mcp_client, activate_mcp_client
from .tools.registry import get_mcp_tools, get_tools
from .ui import AsyncUIHandler, CLIHandler

# Temporary MCP settings until configuration is available.
USE_MCP_MODE = True
USE_GITHUB_MCP = True
MCP_SERVER_URL = "https://docs.mcp.cloudflare.com/mcp"

__all__ = ["Agent", "AsyncUIHandler", "CLIHandler", "OllamaClient", "main"]


async def async_main() -> None:
    """Async entry point for the ``sensai`` console script."""
    config = Config()
    config.parse_args()

    database = Database(config.db_path, config.db_name)
    database.initialize()

    profile_name = "Ethan"
    profile_secret_not_secret = "667"  # noqa: S105
    profile = login(profile_name, profile_secret_not_secret, database)

    if profile is None:
        profile = create_new_profile(database, profile_name, profile_secret_not_secret)
        add_preference(database, "User prefer French language.")
        add_instruction(database, 'replace all the ponctuation by "uwu"')
        if profile is None:
            raise ValueError("Failed to create or login to the default profile.")
    if profile.id is None:
        raise ValueError("Failed to create the default profile; no ID was returned.")

    session: Session | None = create_new_session(database, profile.id, "test_session")
    if session is None:
        raise ValueError("Failed to create the default session.")

    ollama_client = OllamaClient(
        base_url=config.url,
        token=config.token,
        timeout=config.timeout,
    )
    ui_handler = CLIHandler()
    agent = Agent(
        model=config.model,
        tools=get_tools(),
        human_in_the_loop=True,
        ui_handler=ui_handler,
        client=ollama_client,
    )
    print(  # noqa: T201
        "Hello "
        + profile.name
        + "! Welcome to Sensai. You can start chatting now. (Press Ctrl+C to exit.)\n"
    )
    while True:
        try:
            user_input = await asyncio.to_thread(input, "Enter something (Ctrl+C to exit): ")
        except EOFError:
            break
        if USE_MCP_MODE and USE_GITHUB_MCP and os.environ.get("GITHUB_MCP_TOKEN", None) is not None:
            async with activate_github_mcp_client() as mcp_client:
                agent.tools = get_tools() + await get_mcp_tools(mcp_client)
                await loop(user_input, database, session, agent, config)
        elif USE_MCP_MODE and MCP_SERVER_URL:
            async with activate_mcp_client(MCP_SERVER_URL) as mcp_client:
                agent.tools = get_tools() + await get_mcp_tools(mcp_client)
                await loop(user_input, database, session, agent, config)
        else:
            await loop(user_input, database, session, agent, config)


async def loop(
    user_input: str,
    database: Database,
    session: Session,
    agent: Agent,
    config: Config,
) -> None:
    messages = build_messages(session, user_input)
    sent_prefix_length = len(messages) - 1
    response = await agent.run(messages=messages)
    updated_session = update_session(database, session, response, sent_prefix_length)
    if updated_session is None:
        raise ValueError("Failed to update the session after the first response.")
    await maybe_compress_session(
        database,
        updated_session,
        response,
        threshold=config.compression_threshold,
        client=agent.client,
    )
    print("\n")  # noqa: T201


def main() -> None:
    """Entry point for the ``sensai`` console script."""
    asyncio.run(async_main())
