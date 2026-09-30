"""Retrieval-augmented generation: turning documents into searchable, embedded chunks."""

from functools import cache
from io import BytesIO
from pathlib import PurePath
from typing import TYPE_CHECKING

from semantic_text_splitter import MarkdownSplitter

from sensai.data.session.chunk import create_chunk
from sensai.data.session.document import Document, create_document

if TYPE_CHECKING:
    from markitdown import MarkItDown

    from sensai.data.database.database import Database
    from sensai.embedder import Embedder

DEFAULT_CHUNK_SIZE = 1500
DEFAULT_CHUNK_OVERLAP = 200


@cache
def _converter() -> "MarkItDown":
    """The shared document-to-Markdown converter, created on first use.

    Importing and creating it takes seconds (it loads a file-type detection model), so it's
    only paid once, and only by runs that actually ingest a document.
    """
    from markitdown import MarkItDown  # noqa: PLC0415 - slow import, see above

    return MarkItDown(enable_plugins=False)


def _extract_text(content: bytes, name: str | None = None) -> str:
    """Convert a document's raw content into Markdown text.

    Handles plain text, Markdown, HTML, PDF and DOCX, among others. The format is guessed
    from `name`'s extension when given, from the content otherwise.

    Raises:
        ValueError: If the format isn't supported, or no text could be extracted from the
            document, e.g. a scanned PDF holding only images.
    """
    from markitdown import MarkItDownException, StreamInfo  # noqa: PLC0415 - see _converter

    label = name or "the document"
    stream_info = StreamInfo(
        filename=name,
        extension=(PurePath(name).suffix or None) if name else None,
    )
    try:
        result = _converter().convert_stream(BytesIO(content), stream_info=stream_info)
    except MarkItDownException as error:
        msg = f"Could not extract text from {label}: {error}"
        raise ValueError(msg) from error
    if not result.text_content.strip():
        msg = f"No text could be extracted from {label}."
        raise ValueError(msg)
    return result.text_content


def split_text(
    text: str, size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP
) -> list[str]:
    """Split Markdown text into chunks of at most `size` characters, on meaningful boundaries.

    Cuts between sections where possible, then between paragraphs, sentences and words,
    without breaking Markdown elements such as lists or code blocks when they fit.
    Each chunk repeats up to `overlap` characters of the previous one, so an idea cut
    between two chunks stays readable in at least one of them.

    Args:
        text (str): The Markdown (or plain) text to split.
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
    return MarkdownSplitter(size, overlap=overlap).chunks(text)


async def ingest_document(
    db: "Database",
    embedder: "Embedder",
    message_id: int,
    content: bytes,
    name: str | None = None,
) -> Document:
    """Store a document attached to a message, along with its embedded chunks.

    The content is converted to Markdown text (PDF, DOCX, HTML, plain text...), split into
    chunks, and the chunks are embedded before anything is written, so the database isn't locked
    during the request to Ollama, and are then written with the document in a single
    transaction, so a document is never left half-chunked.

    Args:
        db (Database): The database to write to.
        embedder (Embedder): The embedder turning the chunks into vectors.
        message_id (int): The ID of the message the document is attached to.
        content (bytes): The document's raw content, kept as is in the document.
        name (str | None, optional): The document's file name, whose extension tells its
            format. Default is None, which guesses the format from the content.

    Returns:
        Document: The newly created document, including its assigned ID.

    Raises:
        ValueError: If the format isn't supported or no text could be extracted from it.
    """
    pieces = split_text(_extract_text(content, name))
    vectors = await embedder.embed_documents(pieces)
    with db.database.atomic():
        document = create_document(db, message_id, content)
        if document.id is None:
            msg = "Failed to create the document; no ID was returned."
            raise RuntimeError(msg)
        for position, (piece, vector) in enumerate(zip(pieces, vectors, strict=True)):
            create_chunk(db, document.id, position, piece, vector)
    return document
