"""Tests for the ``sensai.data.session.chunk`` module."""

import peewee
import pytest

from sensai.data.database.database import Database
from sensai.data.session.chunk import (
    EMBEDDING_DIMENSIONS,
    Chunk,
    create_chunk,
    get_chunks_by_document,
    search_chunks,
    search_chunks_by_keywords,
    search_chunks_hybrid,
)
from sensai.data.session.document import Document, create_document
from sensai.data.session.message import create_message
from sensai.data.session.session import create_session


def _embedding(*values: float) -> list[float]:
    """A full-size embedding starting with ``values``, zero-padded."""
    return [*values, *[0.0] * (EMBEDDING_DIMENSIONS - len(values))]


def _vector_rowids(db: Database) -> list[int]:
    cursor = db.database.execute_sql("SELECT rowid FROM chunk_vec ORDER BY rowid")
    return [row[0] for row in cursor.fetchall()]


@pytest.fixture
def message_id(db: Database, profile_id: int) -> int:
    session = create_session(db, profile_id)
    assert session.id is not None
    message = create_message(db, session.id, "hi", "user", 1.0)
    assert message.id is not None
    return message.id


@pytest.fixture
def document_id(db: Database, message_id: int) -> int:
    document = create_document(db, message_id, b"raw bytes")
    assert document.id is not None
    return document.id


def test_create_chunk_stores_text_and_embedding(db: Database, document_id: int) -> None:
    chunk = create_chunk(db, document_id, 0, "hello", _embedding(1.0))

    assert chunk.id is not None
    assert chunk.document_id == document_id
    assert chunk.position == 0
    assert chunk.content == "hello"
    assert _vector_rowids(db) == [chunk.id]


def test_create_chunk_rejects_unknown_document(db: Database) -> None:
    with pytest.raises(peewee.IntegrityError):
        create_chunk(db, 9999, 0, "hello", _embedding(1.0))


def test_create_chunk_rejects_duplicate_position(db: Database, document_id: int) -> None:
    create_chunk(db, document_id, 0, "first", _embedding(1.0))

    with pytest.raises(peewee.IntegrityError):
        create_chunk(db, document_id, 0, "second", _embedding(1.0))


def test_create_chunk_with_wrong_dimensions_leaves_no_chunk(db: Database, document_id: int) -> None:
    with pytest.raises(peewee.OperationalError):
        create_chunk(db, document_id, 0, "hello", [1.0, 0.0])

    assert get_chunks_by_document(db, document_id) == []


def test_get_chunks_by_document_returns_chunks_in_position_order(
    db: Database, document_id: int
) -> None:
    create_chunk(db, document_id, 1, "second", _embedding(1.0))
    create_chunk(db, document_id, 0, "first", _embedding(1.0))

    chunks = get_chunks_by_document(db, document_id)

    assert [c.content for c in chunks] == ["first", "second"]


def test_search_chunks_returns_closest_first_with_distance(db: Database, document_id: int) -> None:
    create_chunk(db, document_id, 0, "far", _embedding(0.0, 1.0))
    create_chunk(db, document_id, 1, "exact", _embedding(1.0, 0.0))
    create_chunk(db, document_id, 2, "close", _embedding(0.9, 0.1))

    chunks = search_chunks(db, _embedding(1.0, 0.0), k=2)

    assert [c.content for c in chunks] == ["exact", "close"]
    assert chunks[0].distance == pytest.approx(0.0, abs=1e-6)
    assert chunks[0].distance is not None
    assert chunks[1].distance is not None
    assert chunks[1].distance > chunks[0].distance


def test_search_chunks_only_searches_given_documents(
    db: Database, message_id: int, document_id: int
) -> None:
    other = create_document(db, message_id, b"other")
    assert other.id is not None
    create_chunk(db, document_id, 0, "mine", _embedding(0.0, 1.0))
    create_chunk(db, other.id, 0, "other", _embedding(1.0, 0.0))

    chunks = search_chunks(db, _embedding(1.0, 0.0), document_ids=[document_id])

    assert [c.content for c in chunks] == ["mine"]


def test_search_chunks_with_no_documents_returns_nothing(db: Database, document_id: int) -> None:
    create_chunk(db, document_id, 0, "hello", _embedding(1.0))

    assert search_chunks(db, _embedding(1.0), document_ids=[]) == []


def test_deleting_a_document_removes_its_chunks_and_embeddings(
    db: Database, document_id: int
) -> None:
    create_chunk(db, document_id, 0, "hello", _embedding(1.0))

    with db.database.bind_ctx([Document]):
        Document.delete().where(Document.id == document_id).execute()

    with db.database.bind_ctx([Chunk]):
        assert Chunk.select().count() == 0
    assert _vector_rowids(db) == []
    assert search_chunks(db, _embedding(1.0)) == []


def _keyword_rowids(db: Database, keyword: str) -> list[int]:
    cursor = db.database.execute_sql(
        "SELECT rowid FROM chunk_fts WHERE chunk_fts MATCH ?", (keyword,)
    )
    return [row[0] for row in cursor.fetchall()]


def test_search_chunks_by_keywords_ranks_matching_chunks(db: Database, document_id: int) -> None:
    create_chunk(db, document_id, 0, "Le café est bon", _embedding(1.0))
    create_chunk(db, document_id, 1, "Erreur ECONNRESET côté serveur", _embedding(1.0))
    create_chunk(db, document_id, 2, "Serveur en panne, serveur relancé", _embedding(1.0))

    chunks = search_chunks_by_keywords(db, "serveur ECONNRESET ?", k=5)

    assert [c.content for c in chunks] == [
        "Erreur ECONNRESET côté serveur",
        "Serveur en panne, serveur relancé",
    ]
    assert chunks[0].rank is not None
    assert chunks[1].rank is not None
    assert chunks[0].rank < chunks[1].rank


def test_search_chunks_by_keywords_ignores_accents_and_case(db: Database, document_id: int) -> None:
    create_chunk(db, document_id, 0, "Côté serveur", _embedding(1.0))

    chunks = search_chunks_by_keywords(db, "COTE")

    assert [c.content for c in chunks] == ["Côté serveur"]


def test_search_chunks_by_keywords_treats_fts_syntax_as_plain_text(
    db: Database, document_id: int
) -> None:
    create_chunk(db, document_id, 0, "c'est NOT un problème", _embedding(1.0))

    chunks = search_chunks_by_keywords(db, 'c\'est "NOT" (problème) OR* -')

    assert [c.content for c in chunks] == ["c'est NOT un problème"]


def test_search_chunks_by_keywords_without_words_returns_nothing(
    db: Database, document_id: int
) -> None:
    create_chunk(db, document_id, 0, "hello", _embedding(1.0))

    assert search_chunks_by_keywords(db, " ?! ") == []
    assert search_chunks_by_keywords(db, "hello", document_ids=[]) == []


def test_search_chunks_by_keywords_only_searches_given_documents(
    db: Database, message_id: int, document_id: int
) -> None:
    other = create_document(db, message_id, b"other")
    assert other.id is not None
    create_chunk(db, document_id, 0, "serveur mine", _embedding(1.0))
    create_chunk(db, other.id, 0, "serveur other", _embedding(1.0))

    chunks = search_chunks_by_keywords(db, "serveur", document_ids=[document_id])

    assert [c.content for c in chunks] == ["serveur mine"]


def test_keyword_index_follows_chunk_updates_and_deletes(db: Database, document_id: int) -> None:
    chunk = create_chunk(db, document_id, 0, "ancien", _embedding(1.0))

    with db.database.bind_ctx([Chunk]):
        Chunk.update(content="nouveau").where(Chunk.id == chunk.id).execute()
    assert _keyword_rowids(db, "ancien") == []
    assert _keyword_rowids(db, "nouveau") == [chunk.id]

    with db.database.bind_ctx([Document]):
        Document.delete().where(Document.id == document_id).execute()
    assert _keyword_rowids(db, "nouveau") == []


def test_search_chunks_hybrid_merges_both_rankings(db: Database, document_id: int) -> None:
    create_chunk(db, document_id, 0, "sens proche", _embedding(1.0, 0.0))
    create_chunk(db, document_id, 1, "code ECONNRESET", _embedding(0.0, 1.0))
    create_chunk(db, document_id, 2, "sans rapport", _embedding(0.0, 0.0, 1.0))

    chunks = search_chunks_hybrid(db, "ECONNRESET", _embedding(1.0, 0.0), k=2)

    assert {c.content for c in chunks} == {"sens proche", "code ECONNRESET"}
    by_content = {c.content: c for c in chunks}
    assert by_content["sens proche"].distance is not None
    assert by_content["code ECONNRESET"].rank is not None


def test_search_chunks_hybrid_favors_chunks_found_by_both(db: Database, document_id: int) -> None:
    create_chunk(db, document_id, 0, "sens seulement", _embedding(1.0, 0.0))
    create_chunk(db, document_id, 1, "serveur et sens", _embedding(0.9, 0.1))
    create_chunk(db, document_id, 2, "serveur seulement", _embedding(0.0, 1.0))
    for position, weight in enumerate([0.8, 0.7, 0.6], start=3):
        create_chunk(db, document_id, position, "remplissage", _embedding(weight, 1 - weight))

    chunks = search_chunks_hybrid(db, "serveur", _embedding(1.0, 0.0), k=1)

    assert chunks[0].content == "serveur et sens"
    assert chunks[0].distance is not None
    assert chunks[0].rank is not None
