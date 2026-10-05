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
    assert split_text("# Titre\n\nUn paragraphe.\n\n") == ["# Titre\n\nUn paragraphe."]


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


def _pdf(text: str) -> bytes:
    """A minimal one-page PDF showing ``text``."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
            b" /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return pdf


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "name", "expected"),
    [
        (_pdf("Le serveur redemarre a minuit."), "notes.pdf", "Le serveur redemarre a minuit."),
        (_pdf("Sans nom de fichier."), None, "Sans nom de fichier."),
        (b"<h1>Titre</h1><p>Du texte.</p>", "page.html", "# Titre\n\nDu texte."),
        ("Côté serveur.".encode(), "notes.txt", "Côté serveur."),
    ],
)
async def test_ingest_document_extracts_text_from_supported_formats(
    db: Database, message_id: int, content: bytes, name: str | None, expected: str
) -> None:
    document = await ingest_document(db, Embedder(MockClient()), message_id, content, name)

    assert document.id is not None
    assert [chunk.content for chunk in get_chunks_by_document(db, document.id)] == [expected]
    assert document.content == content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "name", "error"),
    [
        (b"\x00\x01\xff\xfe" * 10, None, "Could not extract text"),
        (b"%PDF-1.4\n" + bytes(range(256)) * 4, "broken.pdf", "Could not extract text"),
        (_pdf(""), "scan.pdf", "No text could be extracted from scan.pdf"),
        (b" \n\n ", "empty.txt", "No text could be extracted from empty.txt"),
    ],
)
async def test_ingest_document_rejects_documents_without_text_before_storing(
    db: Database, message_id: int, content: bytes, name: str | None, error: str
) -> None:
    client = MockClient()

    with pytest.raises(ValueError, match=error):
        await ingest_document(db, Embedder(client), message_id, content, name)

    assert client.requests == []
    with db.database.bind_ctx([Document]):
        assert Document.select().count() == 0


@pytest.mark.asyncio
async def test_ingest_document_rolls_back_when_a_chunk_fails(db: Database) -> None:
    with pytest.raises(peewee.IntegrityError):
        await ingest_document(db, Embedder(MockClient()), 9999, b"texte")

    with db.database.bind_ctx([Document]):
        assert Document.select().count() == 0
