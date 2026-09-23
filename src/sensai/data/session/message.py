"""Message for handling chat messages data, including content and associated documents."""

from dataclasses import dataclass, field
from sqlite3 import Row

from sensai.data.database.database import Database

from .document import Document


@dataclass
class Message:
    """A chat message, mirroring the `message` table."""

    session_id: int
    content: str
    role: str
    response_time: float
    id: int | None = None
    timestamp: str | None = None
    documents: list[Document] = field(default_factory=list)
    # TODO: not loaded here,needs RAG (convert + vectorize + retrieve relevant chunks)
    # before attaching to a message


def _row_to_message(row: Row) -> Message:
    return Message(
        id=row["id"],
        content=row["content"],
        role=row["role"],
        response_time=row["response_time"],
        session_id=row["session_id"],
        timestamp=row["timestamp"],
    )


def create_message(
    db: Database, session_id: int, content: str, role: str, response_time: float
) -> Message:
    """Create a new message in a session.

    Args:
        db (Database): The database to write to.
        session_id (int): The ID of the session the message belongs to.
        content (str): The message content.
        role (str): The role of the message's author (e.g. "user", "assistant", "tool").
        response_time (float): The time the message became available, in seconds since the epoch.

    Returns:
        Message: The newly created message, including its assigned ID.
    """
    cursor = db.execute(
        "INSERT INTO message (content, role, response_time, session_id) VALUES (?, ?, ?, ?)",
        (content, role, response_time, session_id),
    )
    if cursor.lastrowid is None:
        raise ValueError("Failed to create a new message; no ID was returned.")
    message = get_message(db, cursor.lastrowid)
    if message is None:
        raise ValueError(
            f"Failed to retrieve the newly created message with ID {cursor.lastrowid}."
        )
    return message


def get_message(db: Database, message_id: int) -> Message | None:
    """Retrieve a message by its ID.

    Args:
        db (Database): The database to read from.
        message_id (int): The unique identifier for the message.

    Returns:
        Message | None: The message if found, otherwise None.
    """
    cursor = db.execute(
        "SELECT id, content, role, response_time, session_id, timestamp FROM message WHERE id = ?",
        (message_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_message(row)


def get_messages_by_session(db: Database, session_id: int) -> list[Message]:
    """Retrieve all messages belonging to a session, oldest first.

    Args:
        db (Database): The database to read from.
        session_id (int): The unique identifier for the session.

    Returns:
        list[Message]: The messages belonging to the session.
    """
    cursor = db.execute(
        "SELECT id, content, role, response_time, session_id, timestamp "
        "FROM message WHERE session_id = ? ORDER BY timestamp",
        (session_id,),
    )
    return [_row_to_message(row) for row in cursor.fetchall()]
