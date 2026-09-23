"""Session for handling chat sessions data, including messages and documents."""

from dataclasses import dataclass, field
from sqlite3 import Row

from sensai.data.database.database import Database

from .message import Message, get_messages_by_session


@dataclass
class Session:
    """A chat session, mirroring the `session` table, with its messages."""

    profile_id: int
    name: str | None = None
    id: int | None = None
    created_at: str | None = None
    prompt_eval_count: int = 0
    eval_count: int = 0
    token_used: int = 0
    messages: list[Message] = field(default_factory=list)


def _row_to_session(db: Database, row: Row) -> Session:
    return Session(
        id=row["id"],
        name=row["name"],
        profile_id=row["profile_id"],
        created_at=row["created_at"],
        prompt_eval_count=row["prompt_eval_count"],
        eval_count=row["eval_count"],
        token_used=row["token_used"],
        messages=get_messages_by_session(db, row["id"]),
    )


def create_session(db: Database, profile_id: int, name: str | None = None) -> Session:
    """Create a new session for the given profile.

    Args:
        db (Database): The database to write to.
        profile_id (int): The ID of the profile the session belongs to.
        name (str, optional): A display name for the session. Default is None.

    Returns:
        Session: The newly created session, including its assigned ID.
    """
    cursor = db.execute(
        "INSERT INTO session (name, profile_id) VALUES (?, ?)",
        (name, profile_id),
    )
    if cursor.lastrowid is None:
        raise ValueError("Failed to create a new session; no ID was returned.")
    session = get_session(db, cursor.lastrowid)
    if session is None:
        raise ValueError(
            f"Failed to retrieve the newly created session with ID {cursor.lastrowid}."
        )
    return session


def get_session(db: Database, session_id: int) -> Session | None:
    """Retrieve a session by its ID.

    Args:
        db (Database): The database to read from.
        session_id (int): The unique identifier for the session.

    Returns:
        Session | None: The session if found, otherwise None.
    """
    cursor = db.execute(
        "SELECT id, name, profile_id, created_at, prompt_eval_count, eval_count, token_used "
        "FROM session WHERE id = ?",
        (session_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_session(db, row)


def update_session(db: Database, session_id: int, name: str) -> None:
    """Update a session's name.

    Args:
        db (Database): The database to write to.
        session_id (int): The unique identifier for the session.
        name (str): The new name for the session.
    """
    db.execute(
        "UPDATE session SET name = ? WHERE id = ?",
        (name, session_id),
    )


def add_session_usage(
    db: Database, session_id: int, prompt_eval_count: int, eval_count: int, token_used: int
) -> None:
    """Accumulate token usage onto a session's running totals.

    Args:
        db (Database): The database to write to.
        session_id (int): The unique identifier for the session.
        prompt_eval_count (int): The prompt evaluation count to add.
        eval_count (int): The evaluation count to add.
        token_used (int): The number of tokens used to add.
    """
    db.execute(
        "UPDATE session "
        "SET prompt_eval_count = prompt_eval_count + ?, "
        "eval_count = eval_count + ?, "
        "token_used = token_used + ? "
        "WHERE id = ?",
        (prompt_eval_count, eval_count, token_used, session_id),
    )
