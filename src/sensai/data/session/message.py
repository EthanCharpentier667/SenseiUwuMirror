"""Message for handling chat messages data, including content and associated documents."""

from typing import TYPE_CHECKING, cast

from peewee import SQL, CharField, DateTimeField, FloatField, IntegerField, TextField

from sensai.data.database.base_model import BaseModel

from .document import Document

if TYPE_CHECKING:
    from sensai.data.database.database import Database


class Message(BaseModel):
    """A chat message, mirroring the `message` table."""

    session_id = IntegerField(
        index=True, constraints=[SQL('REFERENCES "session" ("id") ON DELETE CASCADE')]
    )
    content = TextField()
    role = CharField()
    response_time = FloatField()
    timestamp = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])


def create_message(
    db: "Database", session_id: int, content: str, role: str, response_time: float
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
    with db.database.bind_ctx([Message]):
        return Message.create(
            session_id=session_id, content=content, role=role, response_time=response_time
        )


def delete_message(db: "Database", message_id: int) -> None:
    """Delete a message by its ID.

    Args:
        db (Database): The database to write to.
        message_id (int): The unique identifier for the message to delete.
    """
    with db.database.bind_ctx([Message]):
        Message.delete().where(Message.id == message_id).execute()


def get_message(db: "Database", message_id: int) -> Message | None:
    """Retrieve a message by its ID.

    Args:
        db (Database): The database to read from.
        message_id (int): The unique identifier for the message.

    Returns:
        Message | None: The message if found, otherwise None.
    """
    with db.database.bind_ctx([Message]):
        return Message.get_or_none(Message.id == message_id)


def get_messages_by_session(db: "Database", session_id: int) -> list[Message]:
    """Retrieve all messages belonging to a session, oldest first.

    Args:
        db (Database): The database to read from.
        session_id (int): The unique identifier for the session.

    Returns:
        list[Message]: The messages belonging to the session.
    """
    with db.database.bind_ctx([Message]):
        return list(
            Message.select()
            .where(Message.session_id == session_id)
            .order_by(Message.timestamp, Message.id)
        )


def get_document_ids_by_session(db: "Database", session_id: int) -> list[int]:
    """Retrieve all document IDs attached to messages in a session.

    Args:
        db (Database): The database to read from.
        session_id (int): The unique identifier for the session.

    Returns:
        list[int]: The IDs of the documents attached to the messages in the session.
    """
    with db.database.bind_ctx([Document, Message]):
        query = (
            Document.select(Document.id)
            .join(Message, on=(Document.message_id == Message.id))
            .where(Message.session_id == session_id)
        )
        return [cast("int", document.id) for document in query]
