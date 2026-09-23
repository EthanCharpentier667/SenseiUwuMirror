"""Sensai: LLM chatbot with unlimited functionalities."""

from pathlib import Path
from typing import TYPE_CHECKING

from .data.database.database import Database
from .data.profile.manager import add_instruction, add_preference, create_profile
from .data.session.manager import build_messages, create_new_session, update_session
from .requester import get_sensei_response
from .tools.registry import get_all_tools

if TYPE_CHECKING:
    from .data.session.session import Session

SCHEMA_PATH = Path(__file__).parent / "data" / "database" / "schema.sql"


def main() -> None:
    """Entry point for the ``sensai`` console script."""
    database = Database("./", SCHEMA_PATH.read_text(), "sensai.db")
    database.initialize()

    # Creating a profile
    profile = create_profile(database, "Ethan", "667")
    add_preference(database, "User prefer French language.")
    add_instruction(database, 'replace all the "the" (or traduction) by uwu')
    if profile.id is None:
        raise ValueError("Failed to create the default profile; no ID was returned.")

    # Creating a new session for the profile
    session: Session | None = create_new_session(database, profile.id, "test_session")
    if session is None:
        raise ValueError("Failed to create the default session.")

    # First request to Sensei
    response = get_sensei_response(
        prompt="Hello, Sensei! How are you doing today? Who is sweetie fox?",
        stream=True,
        tools=get_all_tools(),
    )
    session = update_session(database, session, response)
    if session is None:
        raise ValueError("Failed to update the session after the first response.")

    # Second request to Sensei, using the session's history
    print("\n---------------\n")  # noqa: T201
    response2 = get_sensei_response(
        messages=build_messages(
            session, "Can you summarize the previous response and demands in one sentence?"
        ),
        stream=True,
        tools=get_all_tools(),
    )
    session = update_session(database, session, response2)
    if session is None:
        raise ValueError("Failed to update the session after the second response.")
    print("\n---------------\n")  # noqa: T201
