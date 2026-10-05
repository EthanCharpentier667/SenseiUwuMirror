"""Sensai: LLM chatbot with unlimited functionalities."""

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

from sensai.mcp.github_mcp import GitHubMCP
from sensai.mcp.sensai_client import SensAIClient

from .agent import Agent
from .client import OllamaClient
from .config import Config
from .data.database.database import Database
from .data.profile.manager import add_instruction, add_preference, create_new_profile, login
from .data.session.manager import (
    build_messages,
    create_new_session,
    maybe_compress_session,
    retrieve_chunks,
    update_session,
)
from .data.session.message import create_message, delete_message
from .data.session.session import Session
from .embedder import Embedder
from .rag import ingest_document
from .tools.registry import get_mcp_tools, get_tools
from .ui import AsyncUIHandler, CLIHandler

# Temporary MCP settings until configuration is available.
USE_MCP_MODE = True
USE_GITHUB_MCP = True
MCP_SERVER_URL = "https://docs.mcp.cloudflare.com/mcp"

__all__ = ["Agent", "AsyncUIHandler", "CLIHandler", "OllamaClient", "main"]


@dataclass(frozen=True)
class ConversationRuntime:
    """Dependencies shared by every turn of a conversation."""

    database: Database
    agent: Agent
    embedder: Embedder
    compression_threshold: int


def _create_file_message(database: Database, session: Session, file_path: Path) -> int:
    """Create a session message for an attached file and return its ID."""
    if session.id is None:
        raise ValueError("Cannot attach a file to a session without an ID.")
    file_message = create_message(
        db=database,
        session_id=session.id,
        content=f"File: {file_path}",
        role="user",
        response_time=0.0,
    )
    if file_message.id is None:
        raise ValueError("Failed to create the file message; no ID was returned.")
    return file_message.id


async def _ingest_files(
    files: list[Path], database: Database, session: Session, embedder: Embedder
) -> None:
    """Attach CLI files to the session and index their contents."""
    for file_path in files:
        try:
            content = file_path.read_bytes()
            message_id = _create_file_message(database, session, file_path)
            try:
                await ingest_document(database, embedder, message_id, content, file_path.name)
            except ValueError:
                delete_message(database, message_id)
                raise
        except Exception as error:  # noqa: BLE001
            print(f"Error reading file {file_path}: {error}")  # noqa: T201
        else:
            print(f"Successfully ingested file: {file_path}")  # noqa: T201


async def async_main() -> None:
    """Async entry point for the sensai console script."""
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

    session = create_new_session(database, profile.id, "test_session")
    if session is None:
        raise ValueError("Failed to create the default session.")

    ollama_client = OllamaClient(
        base_url=config.url,
        token=config.token,
        timeout=config.timeout,
    )
    embedder = Embedder(ollama_client)
    agent = Agent(
        model=config.model,
        tools=get_tools(),
        human_in_the_loop=True,
        ui_handler=CLIHandler(),
        client=ollama_client,
    )
    runtime = ConversationRuntime(database, agent, embedder, config.compression_threshold)
    await _ingest_files(config.files, database, session, embedder)

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
        if USE_MCP_MODE and USE_GITHUB_MCP and os.environ.get("GITHUB_MCP_TOKEN") is not None:
            async with GitHubMCP().activate() as mcp_client:
                agent.tools = get_tools() + await get_mcp_tools(mcp_client)
                session = await loop(user_input, session, runtime)
        elif USE_MCP_MODE and MCP_SERVER_URL:
            async with SensAIClient(MCP_SERVER_URL).activate() as mcp_client:
                agent.tools = get_tools() + await get_mcp_tools(mcp_client)
                session = await loop(user_input, session, runtime)
        else:
            session = await loop(user_input, session, runtime)


async def loop(user_input: str, session: Session, runtime: ConversationRuntime) -> Session:
    """Answer one turn with retrieved context and persist the resulting session."""
    retrieved = await retrieve_chunks(runtime.database, runtime.embedder, session, user_input)
    messages = build_messages(session, user_input, retrieved)
    sent_prefix_length = len(messages) - 1
    response = await runtime.agent.run(messages=messages)
    updated_session = update_session(runtime.database, session, response, sent_prefix_length)
    if updated_session is None:
        raise ValueError("Failed to update the session after the first response.")
    session = await maybe_compress_session(
        runtime.database,
        updated_session,
        response,
        threshold=runtime.compression_threshold,
        client=runtime.agent.client,
    )
    print("\n")  # noqa: T201
    return session


def main() -> None:
    """Entry point for the sensai console script."""
    asyncio.run(async_main())
