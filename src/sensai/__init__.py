"""Sensai: LLM chatbot with unlimited functionalities."""

import asyncio

from sensai.config import Config
from sensai.core.setup import (
    ensure_dev_profile,
    get_or_create_session,
    setup_ai_engine,
    setup_database,
)
from sensai.ui.app import CLIApp

__all__ = ["CLIApp", "main"]


async def async_main() -> None:
    """Async entry point for the ``sensai`` console script."""
    config = Config()
    config.parse_args()

    database = setup_database(config)
    client, agent = setup_ai_engine(config)

    profile = ensure_dev_profile(database)
    session = get_or_create_session(database, profile)

    app = CLIApp(
        agent=agent,
        database=database,
        session=session,
        client=client,
        config=config,
        profile_name=profile.name,
    )
    await app.run()


def main() -> None:
    """Entry point for the ``sensai`` console script."""
    asyncio.run(async_main())
