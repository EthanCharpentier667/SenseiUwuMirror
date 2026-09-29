"""Tests for the ``sensai.rag`` module."""

from itertools import pairwise

import peewee
import pytest

from sensai.client import OllamaClient
from sensai.data.database.database import Database
from sensai.data.session.chunk import EMBEDDING_DIMENSIONS, get_chunks_by_document, search_chunks
from sensai.data.session.document import Document, get_document
from sensai.data.session.message import create_message
from sensai.data.session.session import create_session
from sensai.embedder import Embedder
from sensai.rag import ingest_document, split_text


class MockClient(OllamaClient):
    """Ollama client answering one distinct full-size vector per input."""

    def __init__(self) -> None:
        """Initialize MockClient with no request sent yet."""
        super().__init__(base_url="http://localhost:11434/api/chat", token="token", timeout=1.0)  # noqa: S106
        self.requests: list[list[str]] = []

    async def embed(self, inputs: list[str], model: str) -> list[list[float]]:  # noqa: ARG002
        self.requests.append(inputs)
        return [
            [1.0 if dimension == i else 0.0 for dimension in range(EMBEDDING_DIMENSIONS)]
            for i in range(len(inputs))
        ]


@pytest.fixture
def message_id(db: Database, profile_id: int) -> int:
    session = create_session(db, profile_id)
    assert session.id is not None
    message = create_message(db, session.id, "hi", "user", 1.0)
    assert message.id is not None
    return message.id


def test_split_text_keeps_short_text_whole() -> None:
    assert split_text("  Un paragraphe.\n\nUn autre.  ") == ["Un paragraphe.\n\nUn autre."]


def test_split_text_without_words_returns_nothing() -> None:
    assert split_text(" \n\n \r\n ") == []


def test_split_text_cuts_between_paragraphs_within_size() -> None:
    paragraphs = [f"Paragraphe {i}. " + "Une phrase de remplissage. " * 5 for i in range(6)]

    chunks = split_text("\n\n".join(paragraphs), size=400, overlap=0)

    assert len(chunks) > 1
    assert all(len(chunk) <= 400 for chunk in chunks)
    assert all(chunk.startswith("Paragraphe") for chunk in chunks)


def test_split_text_overlaps_consecutive_chunks() -> None:
    words = " ".join(f"mot{i}" for i in range(200))

    chunks = split_text(words, size=100, overlap=30)

    assert all(len(chunk) <= 100 for chunk in chunks)
    for previous, current in pairwise(chunks):
        assert previous.split()[-1] in current.split()


@pytest.mark.parametrize("overlap", [-1, 100, 150])
def test_split_text_rejects_invalid_overlap(overlap: int) -> None:
    with pytest.raises(ValueError, match="overlap"):
        split_text("text", size=100, overlap=overlap)


@pytest.mark.asyncio
async def test_ingest_document_stores_document_and_searchable_chunks(
    db: Database, message_id: int
) -> None:
    client = MockClient()
    content = "\n\n".join(f"Paragraphe {i} " + "mot " * 400 for i in range(3)).encode()

    document = await ingest_document(db, Embedder(client), message_id, content)

    assert document.id is not None
    stored = get_document(db, document.id)
    assert stored is not None
    assert stored.content == content
    chunks = get_chunks_by_document(db, document.id)
    assert len(chunks) > 1
    assert len(client.requests) == 1
    assert client.requests[0] == [f"search_document: {chunk.content}" for chunk in chunks]
    second = [1.0 if dimension == 1 else 0.0 for dimension in range(EMBEDDING_DIMENSIONS)]
    assert search_chunks(db, second, k=1)[0].id == chunks[1].id


@pytest.mark.asyncio
async def test_ingest_document_rejects_non_text_without_storing(
    db: Database, message_id: int
) -> None:
    client = MockClient()

    with pytest.raises(ValueError, match="UTF-8"):
        await ingest_document(db, Embedder(client), message_id, b"%PDF-1.7\n\xff\xfe\x00")

    assert client.requests == []
    with db.database.bind_ctx([Document]):
        assert Document.select().count() == 0


@pytest.mark.asyncio
async def test_ingest_document_rolls_back_when_a_chunk_fails(db: Database) -> None:
    with pytest.raises(peewee.IntegrityError):
        await ingest_document(db, Embedder(MockClient()), 9999, b"texte")

    with db.database.bind_ctx([Document]):
        assert Document.select().count() == 0
