"""Retrieval-augmented generation: turning documents into searchable, embedded chunks."""

from typing import TYPE_CHECKING

from semantic_text_splitter import TextSplitter

from sensai.data.session.chunk import create_chunk
from sensai.data.session.document import Document, create_document

if TYPE_CHECKING:
    from sensai.data.database.database import Database
    from sensai.embedder import Embedder

DEFAULT_CHUNK_SIZE = 1500
DEFAULT_CHUNK_OVERLAP = 200


def _extract_text(content: bytes) -> str:
    """Decode a document's raw content into text.

    Raises:
        ValueError: If the content isn't UTF-8 text, e.g. a PDF or an image.
    """
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        msg = "Only UTF-8 text documents are supported for now."
        raise ValueError(msg) from error


def split_text(
    text: str, size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP
) -> list[str]:
    """Split text into chunks of at most `size` characters, on the most meaningful boundaries.

    Cuts between paragraphs where possible, then between sentences, then between words.
    Each chunk repeats up to `overlap` characters of the previous one, so an idea cut
    between two chunks stays readable in at least one of them.

    Args:
        text (str): The text to split.
        size (int, optional): The maximum length of a chunk, in characters.
            Default is `DEFAULT_CHUNK_SIZE`.
        overlap (int, optional): How many characters of a chunk can be repeated at the
            start of the next one. Default is `DEFAULT_CHUNK_OVERLAP`.

    Returns:
        list[str]: The chunks, in text order. Empty if the text holds no words.

    Raises:
        ValueError: If `overlap` is negative or not smaller than `size`.
    """
    if overlap < 0:
        msg = f"overlap ({overlap}) must not be negative."
        raise ValueError(msg)
    return TextSplitter(size, overlap=overlap).chunks(text)


async def ingest_document(
    db: "Database", embedder: "Embedder", message_id: int, content: bytes
) -> Document:
    """Store a document attached to a message, along with its embedded chunks.

    The chunks are embedded before anything is written, so the database isn't locked
    during the request to Ollama, and are then written with the document in a single
    transaction, so a document is never left half-chunked.

    Args:
        db (Database): The database to write to.
        embedder (Embedder): The embedder turning the chunks into vectors.
        message_id (int): The ID of the message the document is attached to.
        content (bytes): The document's raw content, kept as is in the document.

    Returns:
        Document: The newly created document, including its assigned ID.

    Raises:
        ValueError: If the content isn't UTF-8 text.
    """
    pieces = split_text(_extract_text(content))
    vectors = await embedder.embed_documents(pieces)
    with db.database.atomic():
        document = create_document(db, message_id, content)
        if document.id is None:
            msg = "Failed to create the document; no ID was returned."
            raise RuntimeError(msg)
        for position, (piece, vector) in enumerate(zip(pieces, vectors, strict=True)):
            create_chunk(db, document.id, position, piece, vector)
    return document
