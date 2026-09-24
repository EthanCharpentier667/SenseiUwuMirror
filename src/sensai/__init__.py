"""Sensai: LLM chatbot with unlimited functionalities."""

from typing import TYPE_CHECKING

from .config import Config
from .data.database.database import Database
from .data.profile.manager import add_instruction, add_preference, create_new_profile
from .data.session.manager import (
    build_messages,
    create_new_session,
    maybe_compress_session,
    update_session,
)
from .requester import get_sensei_response
from .tools.registry import get_all_tools

if TYPE_CHECKING:
    from .data.session.session import Session


def main() -> None:
    """Entry point for the ``sensai`` console script."""
    config = Config()
    config.parse_args()

    database = Database(config.db_path, config.schema_path.read_text(), config.db_name)
    database.initialize()

    # Creating a profile
    profile = create_new_profile(database, "Ethan", "667")
    add_preference(database, "User prefer French language.")
    add_instruction(database, 'replace all the ponctuation by "uwu"')
    if profile.id is None:
        raise ValueError("Failed to create the default profile; no ID was returned.")

    # Creating a new session for the profile
    session: Session | None = create_new_session(database, profile.id, "test_session")
    if session is None:
        raise ValueError("Failed to create the default session.")

    # Starting the chat loop
    try:
        print(  # noqa: T201
            "Hello "
            + profile.name
            + "! Welcome to Sensai. You can start chatting now. (Press Ctrl+C to exit.)\n"
        )
        while True:
            user_input = input("Enter something (Ctrl+C to exit): ")
            response = get_sensei_response(
                messages=build_messages(session, user_input),
                model=config.model,
                stream=True,
                tools=get_all_tools(),
            )
            session = update_session(database, session, response)
            if session is None:
                raise ValueError("Failed to update the session after the first response.")
            session = maybe_compress_session(
                database, session, response, threshold=config.compression_threshold
            )
            print("\n")  # noqa: T201

    except KeyboardInterrupt:
        print("\nProgram terminated by user.")  # noqa: T201
