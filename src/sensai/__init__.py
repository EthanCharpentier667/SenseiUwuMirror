"""Sensai: LLM chatbot with unlimited functionalities."""

import asyncio

from rich.console import Console

from sensai.config import Config
from sensai.core.setup import (
    get_or_create_session,
    ingest_initial_files,
    setup_ai_engine,
    setup_database,
)
from sensai.embedder import Embedder
from sensai.ui.app import CLIApp
from sensai.ui.auth import authenticate_user

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
    await app.run()


def main() -> None:
    """Entry point for the ``sensai`` console script."""
    asyncio.run(async_main())
