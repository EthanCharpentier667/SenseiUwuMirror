"""Document for handling documents attached to messages in chat sessions."""

from typing import TYPE_CHECKING

from peewee import SQL, BlobField, DateTimeField, IntegerField

from sensai.data.database.base_model import BaseModel

if TYPE_CHECKING:
    from sensai.data.database.database import Database


class Document(BaseModel):
    """A document attached to a message, mirroring the `document` table."""

    message_id = IntegerField(
        index=True, constraints=[SQL('REFERENCES "message" ("id") ON DELETE CASCADE')]
    )
    # TODO: raw blob, needs RAG (convert + vectorize + retrieve relevant chunks)
    # before use as LLM context
    content = BlobField()
    timestamp = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])


def create_document(db: "Database", message_id: int, content: bytes) -> Document:
    """Create a new document attached to a message.

    Args:
        db (Database): The database to write to.
        message_id (int): The ID of the message the document belongs to.
        content (bytes): The document content.

    Returns:
        Document: The newly created document, including its assigned ID.
    """
    with db.database.bind_ctx([Document]):
        return Document.create(message_id=message_id, content=content)


def get_document(db: "Database", document_id: int) -> Document | None:
    """Retrieve a document by its ID.

    Args:
        db (Database): The database to read from.
        document_id (int): The unique identifier for the document.

    Returns:
        Document | None: The document if found, otherwise None.
    """
    with db.database.bind_ctx([Document]):
        return Document.get_or_none(Document.id == document_id)


def get_documents_by_message(db: "Database", message_id: int) -> list[Document]:
    """Retrieve all documents attached to a message.

    Args:
        db (Database): The database to read from.
        message_id (int): The unique identifier for the message.

    Returns:
        list[Document]: The documents attached to the message.
    """
    with db.database.bind_ctx([Document]):
        return list(
            Document.select().where(Document.message_id == message_id).order_by(Document.timestamp)
        )
