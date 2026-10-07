"""Orchestration and setup functions for Sensai components."""

from pathlib import Path

from rich.console import Console

from sensai.agent import Agent
from sensai.client import OllamaClient
from sensai.config import Config
from sensai.data.database.database import Database
from sensai.data.profile.profile import Profile
from sensai.data.session.manager import create_new_session
from sensai.data.session.message import create_message, delete_message
from sensai.data.session.session import Session
from sensai.embedder import Embedder
from sensai.rag import ingest_document
from sensai.tools.registry import get_all_tools
from sensai.ui.cli import CLIHandler


def setup_database(config: Config) -> Database:
    """Initialize and return the database connection."""
    database = Database(config.db_path, config.db_name)
    database.initialize()
    return database


def setup_ai_engine(config: Config) -> tuple[OllamaClient, Agent]:
    """Initialize and return the Ollama client and Agent."""
    client = OllamaClient(
        base_url=config.url,
        token=config.token,
        timeout=config.timeout,
        verbose=config.verbose,
    )
    ui_handler = CLIHandler()
    agent = Agent(
        model=config.model,
        tools=get_all_tools(),
        trust_level="none",
        ui_handler=ui_handler,
        client=client,
    )
    return client, agent


def get_or_create_session(database: Database, profile: Profile) -> Session:
    """Create or load a test session for the profile."""
    if profile.id is None:
        msg = "Profile ID cannot be None when creating a session."
        raise ValueError(msg)

    session: Session | None = create_new_session(database, profile.id, "test_session")
    if session is None:
        msg = "Failed to create the default session."
        raise ValueError(msg)
    return session


async def ingest_initial_files(
    database: Database,
    embedder: Embedder,
    session: Session,
    files: list[Path],
    console: Console,
) -> None:
    """Ingest command-line supplied files into the active session.

    Args:
        database: The active database connection.
        embedder: The embedder instance to vectorize document chunks.
        session: The active chat session.
        files: List of file paths to ingest.
        console: The rich console instance for user-facing output.
    """
    if session.id is None:
        return

    for file_path in files:
        try:
            with file_path.open("rb") as f:
                file_content = f.read()
            file_message = create_message(
                db=database,
                session_id=session.id,
                content=f"File: {file_path}",
                role="user",
                response_time=0.0,
            )
            if file_message.id is None:
                continue
            try:
                await ingest_document(
                    database, embedder, file_message.id, file_content, file_path.name
                )
            except ValueError:
                delete_message(database, file_message.id)
                console.print(f"[red]Failed to ingest file: {file_path}[/red]")
            console.print(f"[green]Successfully ingested file: {file_path}[/green]")
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Error reading file {file_path}: {e}[/red]")
