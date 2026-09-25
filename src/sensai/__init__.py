"""Sensai: LLM chatbot with unlimited functionalities."""

import asyncio
from typing import TYPE_CHECKING

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
from .tools.registry import get_all_tools
from .ui import AsyncUIHandler, CLIHandler

__all__ = ["Agent", "AsyncUIHandler", "CLIHandler", "OllamaClient", "main"]

if TYPE_CHECKING:
    from .data.session.session import Session


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
        profile = create_new_profile(database, "Ethan", "667")
        if profile is None:
            raise ValueError("Failed to create or login to the default profile.")
    add_preference(database, "User prefer French language.")
    add_instruction(database, 'replace all the ponctuation by "uwu"')
    if profile.id is None:
        raise ValueError("Failed to create the default profile; no ID was returned.")

    session: Session | None = create_new_session(database, profile.id, "test_session")
    if session is None:
        raise ValueError("Failed to create the default session.")

    ui_handler = CLIHandler()
    agent = Agent(
        model=config.model,
        tools=get_all_tools(),
        human_in_the_loop=True,
        ui_handler=ui_handler,
    )

    try:
        print(  # noqa: T201
            "Hello "
            + profile.name
            + "! Welcome to Sensai. You can start chatting now. (Press Ctrl+C to exit.)\n"
        )
        while True:
            user_input = await asyncio.to_thread(input, "Enter something (Ctrl+C to exit): ")
            messages = build_messages(session, user_input)
            sent_prefix_length = len(messages) - 1
            response = await agent.run(messages=messages)
            session = update_session(database, session, response, sent_prefix_length)
            if session is None:
                raise ValueError("Failed to update the session after the first response.")
            session = await maybe_compress_session(
                database, session, response, threshold=config.compression_threshold
            )
            print("\n")  # noqa: T201

    except KeyboardInterrupt:
        print("\nProgram terminated by user.")  # noqa: T201


def main() -> None:
    """Entry point for the ``sensai`` console script."""
    asyncio.run(async_main())
