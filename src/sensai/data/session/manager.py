"""Manager for handling chat sessions, messages, and documents."""

from typing import Any

from sensai.data.database.database import Database
from sensai.requester import Response

from .message import create_message
from .session import Session, add_session_usage, create_session, get_session


class SessionManager:
    """Holds the process-wide currently active session."""

    current_session: Session | None = None


def get_current_session() -> Session | None:
    """Retrieve the current active session.

    Returns:
        Session | None: The current session if set, otherwise None.
    """
    return SessionManager.current_session


def set_current_session(session: Session) -> None:
    """Set the current active session.

    Args:
        session (Session): The session to set as current.
    """
    SessionManager.current_session = session


def clear_current_session() -> None:
    """Clear the current active session."""
    SessionManager.current_session = None


def create_new_session(db: Database, profile_id: int, name: str | None = None) -> Session:
    """Create a new session for the given profile and set it as the current session.

    Args:
        db (Database): The database to write to.
        profile_id (int): The ID of the profile the session belongs to.
        name (str, optional): A display name for the session. Default is None.

    Returns:
        Session: The newly created session, including its assigned ID.
    """
    session = create_session(db, profile_id, name)
    set_current_session(session)
    return session


def update_session(db: Database, session: Session, response: Response) -> Session | None:
    """Persist a response's new messages and usage onto an existing session.

    ``response.messages`` echoes everything sent to the API for this exchange, which
    includes the session's already-persisted history when the request was built with
    ``build_messages``. Only the messages past that history are new to this turn, so
    only those are persisted here to avoid re-inserting duplicates of past messages.

    Args:
        db (Database): The database to write to.
        session (Session): The session to update.
        response (Response): The response to persist.

    Returns:
        Session | None: The updated session if successful, otherwise None.
    """
    if session.id is None:
        return None
    new_messages = response.messages[len(session.messages) :]
    for message in new_messages:
        add_message_to_current_session(db, message.content, message.role, message.response_time)
    add_session_usage(
        db, session.id, response.prompt_eval_count, response.eval_count, response.token_used
    )
    return get_session(db, session.id)


def build_messages(session: Session, prompt: str) -> list[dict[str, Any]]:
    """Build the API-ready message list for a new prompt, prefixed with a session's history.

    Args:
        session (Session): The session whose persisted messages provide the context.
        prompt (str): The new user prompt to append after the session's history.

    Returns:
        list[dict[str, Any]]: The conversation history followed by the new prompt, in the
            raw ``{"role": ..., "content": ...}`` shape the Sensei API expects.
    """
    history = [{"role": message.role, "content": message.content} for message in session.messages]
    return [*history, {"role": "user", "content": prompt}]


def get_session_by_id(db: Database, session_id: int) -> Session | None:
    """Retrieve a session by its ID.

    Args:
        db (Database): The database to read from.
        session_id (int): The unique identifier for the session.

    Returns:
        Session | None: The session if found, otherwise None.
    """
    return get_session(db, session_id)


def get_current_session_id() -> int | None:
    """Retrieve the ID of the current active session.

    Returns:
        int | None: The ID of the current session if set, otherwise None.
    """
    current_session = get_current_session()
    return current_session.id if current_session else None


def is_current_session(session_id: int) -> bool:
    """Check if the given session ID matches the current active session.

    Args:
        session_id (int): The session ID to check.

    Returns:
        bool: True if the given session ID matches the current session, otherwise False.
    """
    current_session = get_current_session()
    return current_session is not None and current_session.id == session_id


def add_message_to_current_session(
    db: Database, content: str, role: str, response_time: float
) -> None:
    """Add a new message to the current active session.

    Args:
        db (Database): The database to write to.
        content (str): The message content.
        role (str): The role of the message's author (e.g. "user", "assistant", "tool").
        response_time (float): The time the message became available, in seconds since the epoch.

    Raises:
        ValueError: If there is no current active session.
    """
    current_session = get_current_session()
    if current_session is None:
        raise ValueError("No current session is set.")

    current_session_id = current_session.id
    if current_session_id is None:
        raise ValueError("Current session does not have a valid ID.")
    create_message(db, current_session_id, content, role, response_time)
