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
from sensai.persona.manager import get_persona, list_personas, load_personas
from sensai.ui.app import CLIApp
from sensai.ui.auth import authenticate_user

__all__ = ["CLIApp", "main"]


async def async_main() -> None:
    """Async entry point for the ``sensai`` console script."""
    config = Config()
    config.parse_args()

    if config.list_personas:
        try:
            personas = load_personas(config.personas_file)
            keys = list_personas(personas)
            if keys:
                print("Available personas:")  # noqa: T201
                for key in keys:
                    p = personas[key]
                    print(f"  {key}: {p.name} — {p.description}")  # noqa: T201
            else:
                print("No personas found.")  # noqa: T201
        except FileNotFoundError:
            print(f"Warning: personas file not found: {config.personas_file}")  # noqa: T201
        return

    database = setup_database(config)
    client, agent = setup_ai_engine(config)
    embedder = Embedder(client)

    if config.persona:
        try:
            personas = load_personas(config.personas_file)
            persona = get_persona(personas, config.persona)
            if persona is not None:
                agent.system_prompt = persona.system_prompt
            else:
                print(f"Warning: persona '{config.persona}' not found.")  # noqa: T201
        except FileNotFoundError:
            print(f"Warning: personas file not found: {config.personas_file}")  # noqa: T201
        except ValueError as exc:
            print(f"Warning: invalid personas file: {exc}")  # noqa: T201

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
