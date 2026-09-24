"""Document for handling documents attached to messages in chat sessions."""

from dataclasses import dataclass

from sensai.data.database.database import Database


@dataclass(frozen=True, slots=True)
class Document:
    """A document attached to a message, mirroring the `document` table."""

    message_id: int
    # TODO: raw blob, needs RAG (convert + vectorize + retrieve relevant chunks)
    # before use as LLM context
    content: bytes
    id: int | None = None
    timestamp: str | None = None


def create_document(db: Database, message_id: int, content: bytes) -> Document:
    """Create a new document attached to a message.

    Args:
        db (Database): The database to write to.
        message_id (int): The ID of the message the document belongs to.
        content (bytes): The document content.

    Returns:
        Document: The newly created document, including its assigned ID.
    """
    cursor = db.execute(
        "INSERT INTO document (content, message_id) VALUES (?, ?)",
        (content, message_id),
    )
    if cursor.lastrowid is None:
        raise ValueError("Failed to create a new document; no ID was returned.")
    document = get_document(db, cursor.lastrowid)
    if document is None:
        raise ValueError(
            f"Failed to retrieve the newly created document with ID {cursor.lastrowid}."
        )
    return document


def get_document(db: Database, document_id: int) -> Document | None:
    """Retrieve a document by its ID.

    Args:
        db (Database): The database to read from.
        document_id (int): The unique identifier for the document.

    Returns:
        Document | None: The document if found, otherwise None.
    """
    cursor = db.execute(
        "SELECT id, content, message_id, timestamp FROM document WHERE id = ?",
        (document_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return Document(
        id=row["id"],
        content=row["content"],
        message_id=row["message_id"],
        timestamp=row["timestamp"],
    )


def get_documents_by_message(db: Database, message_id: int) -> list[Document]:
    """Retrieve all documents attached to a message.

    Args:
        db (Database): The database to read from.
        message_id (int): The unique identifier for the message.

    Returns:
        list[Document]: The documents attached to the message.
    """
    cursor = db.execute(
        "SELECT id, content, message_id, timestamp "
        "FROM document WHERE message_id = ? ORDER BY timestamp",
        (message_id,),
    )
    return [
        Document(
            id=row["id"],
            content=row["content"],
            message_id=row["message_id"],
            timestamp=row["timestamp"],
        )
        for row in cursor.fetchall()
    ]
