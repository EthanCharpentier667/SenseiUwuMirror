"""Orchestration and setup functions for Sensai components."""

from pathlib import Path

from rich.console import Console

from sensai.agent import Agent
from sensai.client import OllamaClient
from sensai.config import Config
from sensai.data.database.database import Database
from sensai.data.profile.profile import Profile
from sensai.data.session.manager import new_session, set_current_session
from sensai.data.session.message import create_message, delete_message
from sensai.data.session.session import Session
from sensai.features.features import RAG, Features
from sensai.features.rag.embedder import Embedder
from sensai.features.rag.rag import ingest_document
from sensai.features.tools.registry import get_tools
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
        num_ctx=config.num_ctx,
        temperature=config.temperature,
        top_p=config.top_p,
    )
    ui_handler = CLIHandler()
    agent = Agent(
        model=config.model,
        tools=get_tools(),
        trust_level=config.trust_level,
        ui_handler=ui_handler,
        client=client,
        features=config.features,
    )
    agent.structured_output_schema = config.output_schema
    agent.max_turns = config.max_steps
    return client, agent


def setup_embedder(config: Config) -> Embedder:
    """Initialize and return the embedder, with its own client on the embedding URL."""
    client = OllamaClient(
        base_url=config.embed_url,
        token=config.embed_token,
        timeout=config.timeout,
        verbose=config.verbose,
    )
    return Embedder(client)


def start_session(profile: Profile) -> Session:
    """Start an untitled session for the profile, saved once its first message is sent."""
    if profile.id is None:
        msg = "Profile ID cannot be None when creating a session."
        raise ValueError(msg)

    session = new_session(profile.id)
    set_current_session(session)
    return session


async def ingest_initial_files(  # noqa: PLR0913
    database: Database,
    embedder: Embedder,
    session: Session,
    files: list[Path],
    console: Console,
    *,
    features: Features,
) -> None:
    """Ingest command-line supplied files into the active session.

    Args:
        database: The active database connection.
        embedder: The embedder instance to vectorize document chunks.
        session: The active chat session.
        files: List of file paths to ingest.
        console: The rich console instance for user-facing output.
        features: The feature flags; nothing is ingested while RAG is disabled.
    """
    if session.id is None or not files:
        return
    if not features.is_enabled(RAG):
        console.print("[yellow]RAG is disabled: attached files are ignored.[/yellow]")
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
