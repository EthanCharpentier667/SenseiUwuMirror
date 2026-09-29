"""Retrieval-augmented generation: turning documents into searchable, embedded chunks."""

import re
import textwrap
from typing import TYPE_CHECKING

from sensai.data.session.chunk import create_chunk
from sensai.data.session.document import Document, create_document

if TYPE_CHECKING:
    from sensai.data.database.database import Database
    from sensai.embedder import Embedder

DEFAULT_CHUNK_SIZE = 1500
DEFAULT_CHUNK_OVERLAP = 200
_PARAGRAPH_SEPARATOR = "\n\n"


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


def _paragraphs(text: str) -> list[str]:
    """Split text on blank lines, dropping empty paragraphs."""
    paragraphs = re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
    return [paragraph.strip() for paragraph in paragraphs if paragraph.strip()]


def _fit(paragraph: str, size: int) -> list[str]:
    """Split a paragraph into pieces of at most `size` characters, on sentence boundaries.

    A sentence longer than `size` on its own is split on word boundaries instead.
    """
    if len(paragraph) <= size:
        return [paragraph]
    pieces: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[.!?…])\s+", paragraph):
        for part in textwrap.wrap(sentence, size) if len(sentence) > size else [sentence]:
            if current and len(current) + 1 + len(part) > size:
                pieces.append(current)
                current = ""
            current = f"{current} {part}" if current else part
    if current:
        pieces.append(current)
    return pieces


def _tail(text: str, overlap: int) -> str:
    """The last `overlap` characters of a text, starting on a word boundary if possible."""
    if overlap == 0:
        return ""
    tail = text[-overlap:]
    space = tail.find(" ")
    return tail[space + 1 :] if space != -1 else tail


def split_text(
    text: str, size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP
) -> list[str]:
    """Split text into chunks of at most `size` characters, keeping paragraphs together.

    Paragraphs are packed into a chunk until the next one wouldn't fit; a paragraph too
    long for a chunk is split on sentence boundaries, and a sentence too long on word
    boundaries. Each chunk starts with the last `overlap` characters of the previous one,
    so an idea cut between two chunks stays readable in at least one of them.

    Args:
        text (str): The text to split.
        size (int, optional): The maximum length of a chunk, in characters.
            Default is `DEFAULT_CHUNK_SIZE`.
        overlap (int, optional): How many characters of a chunk are repeated at the start
            of the next one. Default is `DEFAULT_CHUNK_OVERLAP`.

    Returns:
        list[str]: The chunks, in text order. Empty if the text holds no words.

    Raises:
        ValueError: If `overlap` leaves no room for new text in a chunk.
    """
    unit_size = size - overlap - len(_PARAGRAPH_SEPARATOR)
    if overlap < 0 or unit_size < 1:
        msg = f"overlap ({overlap}) must be positive and leave room in a chunk of {size}."
        raise ValueError(msg)
    chunks: list[str] = []
    current = ""
    for paragraph in _paragraphs(text):
        for unit in _fit(paragraph, unit_size):
            if current and len(current) + len(_PARAGRAPH_SEPARATOR) + len(unit) > size:
                chunks.append(current)
                current = _tail(current, overlap)
            current = f"{current}{_PARAGRAPH_SEPARATOR}{unit}" if current else unit
    if current:
        chunks.append(current)
    return chunks


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
