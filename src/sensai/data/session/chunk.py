"""Chunk for storing a document's text pieces and their embeddings, searchable for RAG."""

import re
from typing import TYPE_CHECKING

import sqlite_vec
from peewee import SQL, IntegerField, TextField

from sensai.data.database.base_model import BaseModel

if TYPE_CHECKING:
    from sensai.data.database.database import Database

EMBEDDING_DIMENSIONS = 768
_RRF_K = 60

_VECTOR_TABLE_SQL = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vec USING vec0(
    document_id INTEGER PARTITION KEY,
    embedding FLOAT[{EMBEDDING_DIMENSIONS}] DISTANCE_METRIC=cosine
)
"""
_DELETE_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS chunk_vec_after_chunk_delete AFTER DELETE ON chunk
BEGIN
    DELETE FROM chunk_vec WHERE rowid = OLD.id;
END
"""
_TEXT_TABLE_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
    content, content='chunk', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
)
"""
_TEXT_TRIGGERS_SQL = [
    """
    CREATE TRIGGER IF NOT EXISTS chunk_fts_after_chunk_insert AFTER INSERT ON chunk
    BEGIN
        INSERT INTO chunk_fts(rowid, content) VALUES (NEW.id, NEW.content);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS chunk_fts_after_chunk_delete AFTER DELETE ON chunk
    BEGIN
        INSERT INTO chunk_fts(chunk_fts, rowid, content) VALUES ('delete', OLD.id, OLD.content);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS chunk_fts_after_chunk_update AFTER UPDATE OF content ON chunk
    BEGIN
        INSERT INTO chunk_fts(chunk_fts, rowid, content) VALUES ('delete', OLD.id, OLD.content);
        INSERT INTO chunk_fts(rowid, content) VALUES (NEW.id, NEW.content);
    END
    """,
]


class Chunk(BaseModel):
    """A piece of a document's text, mirroring the `chunk` table.

    Its embedding is stored in the `chunk_vec` virtual table and its text is indexed for
    keyword search in the `chunk_fts` one, both under the same id.
    """

    document_id = IntegerField(
        index=True, constraints=[SQL('REFERENCES "document" ("id") ON DELETE CASCADE')]
    )
    position = IntegerField()
    content = TextField()

    distance: float | None = None
    rank: float | None = None

    class Meta:
        """Table options for `chunk`."""

        indexes = ((("document_id", "position"), True),)


def _execute(db: "Database", sql: str, params: tuple[object, ...] = ()) -> None:
    """Run a raw SQL statement, for the virtual table peewee's models can't express."""
    db.database.execute_sql(sql, params)  # type: ignore[no-untyped-call]


def create_chunk_search_tables(db: "Database") -> None:
    """Create the `chunk_vec` and `chunk_fts` virtual tables and their sync triggers.

    Does nothing for the ones that already exist.

    Args:
        db (Database): The database to write to. Its `chunk` table must already exist.
    """
    _execute(db, _VECTOR_TABLE_SQL)
    _execute(db, _DELETE_TRIGGER_SQL)
    _execute(db, _TEXT_TABLE_SQL)
    for trigger in _TEXT_TRIGGERS_SQL:
        _execute(db, trigger)


def create_chunk(
    db: "Database", document_id: int, position: int, content: str, embedding: list[float]
) -> Chunk:
    """Create a new chunk of a document along with its embedding.

    Args:
        db (Database): The database to write to.
        document_id (int): The ID of the document the chunk belongs to.
        position (int): The chunk's index within its document, unique per document.
        content (str): The chunk's text.
        embedding (list[float]): The chunk's embedding, of `EMBEDDING_DIMENSIONS` floats.

    Returns:
        Chunk: The newly created chunk, including its assigned ID.
    """
    with db.database.bind_ctx([Chunk]), db.database.atomic():
        chunk = Chunk.create(document_id=document_id, position=position, content=content)
        _execute(
            db,
            "INSERT INTO chunk_vec(rowid, document_id, embedding) VALUES (?, ?, ?)",
            (chunk.id, document_id, sqlite_vec.serialize_float32(embedding)),
        )
    return chunk


def get_chunks_by_document(db: "Database", document_id: int) -> list[Chunk]:
    """Retrieve all chunks of a document, in document order.

    Args:
        db (Database): The database to read from.
        document_id (int): The unique identifier for the document.

    Returns:
        list[Chunk]: The document's chunks, ordered by position.
    """
    with db.database.bind_ctx([Chunk]):
        return list(Chunk.select().where(Chunk.document_id == document_id).order_by(Chunk.position))


def _document_filter(column: str, document_ids: list[int] | None) -> tuple[str, list[object]]:
    """An SQL `AND column IN (...)` clause and its params, empty when `document_ids` is None."""
    if document_ids is None:
        return "", []
    return f"AND {column} IN ({', '.join('?' * len(document_ids))})", list(document_ids)


def _keywords_query(text: str) -> str:
    """Turn free text into an FTS5 query matching any of its words, each quoted literally."""
    return " OR ".join(f'"{word}"' for word in re.findall(r"\w+", text))


def search_chunks(
    db: "Database", embedding: list[float], k: int = 5, document_ids: list[int] | None = None
) -> list[Chunk]:
    """Retrieve the chunks whose embeddings are closest to a query embedding.

    Args:
        db (Database): The database to read from.
        embedding (list[float]): The query's embedding, of `EMBEDDING_DIMENSIONS` floats.
        k (int, optional): The maximum number of chunks to return. Default is 5.
        document_ids (list[int] | None, optional): Only search these documents' chunks.
            Default is None, which searches every chunk.

    Returns:
        list[Chunk]: The closest chunks, most similar first, each with its cosine `distance`.
    """
    if document_ids == []:
        return []
    document_filter, filter_params = _document_filter("document_id", document_ids)
    params: list[object] = [sqlite_vec.serialize_float32(embedding), k, *filter_params]
    query = f"""
        SELECT chunk.*, nearest.distance
        FROM (
            SELECT rowid, distance FROM chunk_vec
            WHERE embedding MATCH ? AND k = ? {document_filter}
        ) AS nearest
        JOIN chunk ON chunk.id = nearest.rowid
        ORDER BY nearest.distance
    """  # noqa: S608 - only placeholders are interpolated
    with db.database.bind_ctx([Chunk]):
        return list(Chunk.raw(query, *params))


def search_chunks_by_keywords(
    db: "Database", text: str, k: int = 5, document_ids: list[int] | None = None
) -> list[Chunk]:
    """Retrieve the chunks that best match the words of a text, ranked by BM25.

    Accents and case are ignored, and a chunk matches if it contains any of the words.

    Args:
        db (Database): The database to read from.
        text (str): The free text to search for, e.g. the user's question.
        k (int, optional): The maximum number of chunks to return. Default is 5.
        document_ids (list[int] | None, optional): Only search these documents' chunks.
            Default is None, which searches every chunk.

    Returns:
        list[Chunk]: The best matching chunks first, each with its BM25 `rank` (lower is better).
    """
    keywords = _keywords_query(text)
    if not keywords or document_ids == []:
        return []
    document_filter, filter_params = _document_filter("chunk.document_id", document_ids)
    query = f"""
        SELECT chunk.*, bm25(chunk_fts) AS rank
        FROM chunk_fts
        JOIN chunk ON chunk.id = chunk_fts.rowid
        WHERE chunk_fts MATCH ? {document_filter}
        ORDER BY bm25(chunk_fts)
        LIMIT ?
    """  # noqa: S608 - only placeholders are interpolated
    with db.database.bind_ctx([Chunk]):
        return list(Chunk.raw(query, keywords, *filter_params, k))


def search_chunks_hybrid(
    db: "Database",
    text: str,
    embedding: list[float],
    k: int = 5,
    document_ids: list[int] | None = None,
) -> list[Chunk]:
    """Retrieve the most relevant chunks by both meaning and keywords.

    Runs `search_chunks` and `search_chunks_by_keywords` and merges their rankings with
    Reciprocal Rank Fusion, so a chunk ranked well by either search comes out on top.

    Args:
        db (Database): The database to read from.
        text (str): The query's text, for the keyword search.
        embedding (list[float]): The query's embedding, of `EMBEDDING_DIMENSIONS` floats.
        k (int, optional): The maximum number of chunks to return. Default is 5.
        document_ids (list[int] | None, optional): Only search these documents' chunks.
            Default is None, which searches every chunk.

    Returns:
        list[Chunk]: The most relevant chunks first, with `distance` and/or `rank` set by
            whichever search found them.
    """
    candidates = k * 4
    chunks: dict[int, Chunk] = {}
    scores: dict[int, float] = {}
    for results in (
        search_chunks(db, embedding, candidates, document_ids),
        search_chunks_by_keywords(db, text, candidates, document_ids),
    ):
        for position, chunk in enumerate(results):
            if chunk.id is None:
                continue
            found = chunks.setdefault(chunk.id, chunk)
            found.distance = found.distance if found.distance is not None else chunk.distance
            found.rank = found.rank if found.rank is not None else chunk.rank
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1 / (_RRF_K + position + 1)
    best = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)[:k]
    return [chunks[chunk_id] for chunk_id in best]
