"""Tests for the ``sensai.ui.app`` module."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from sensai.data.database.database import Database
from sensai.data.session.document import get_documents_by_message
from sensai.data.session.message import Message, create_message
from sensai.data.session.session import create_session
from sensai.features.rag.embedder import Embedder
from sensai.ui.app import CLIApp
from tests.test_rag import MockClient


def _app(db: Database, profile_id: int, read_documents: list[str]) -> tuple[CLIApp, Message]:
    """A CLIApp holding only what ingesting needs, and its turn's user message."""
    session = create_session(db, profile_id)
    assert session.id is not None
    user = create_message(db, session.id, "Lis mes notes.", "user", 1.0)
    answer = create_message(db, session.id, "C'est lu.", "assistant", 2.0)
    assert user.id is not None
    app = CLIApp.__new__(CLIApp)
    app.database = db
    app.embedder = Embedder(MockClient())
    app.session = SimpleNamespace(messages=[user, answer])  # type: ignore[assignment]
    app.agent = SimpleNamespace(read_documents=read_documents, ui_handler=None)  # type: ignore[assignment]
    return app, user


@pytest.mark.asyncio
async def test_ingest_read_documents_attaches_each_file_once_to_the_turn(
    db: Database, profile_id: int, tmp_path: Path
) -> None:
    path = tmp_path / "notes.md"
    path.write_text("Des notes.", encoding="utf-8")
    app, user = _app(db, profile_id, [str(path), str(path)])

    await app._ingest_read_documents()  # noqa: SLF001

    assert user.id is not None
    documents = get_documents_by_message(db, user.id)
    assert [document.content for document in documents] == [b"Des notes."]


@pytest.mark.asyncio
async def test_ingest_read_documents_skips_content_the_session_already_holds(
    db: Database, profile_id: int, tmp_path: Path
) -> None:
    path = tmp_path / "notes.md"
    path.write_text("Des notes.", encoding="utf-8")
    copy = tmp_path / "copie.md"
    copy.write_text("Des notes.", encoding="utf-8")
    app, user = _app(db, profile_id, [str(path)])
    await app._ingest_read_documents()  # noqa: SLF001
    later = create_message(db, user.session_id, "Relis-les.", "user", 3.0)
    app.session = SimpleNamespace(messages=[later])  # type: ignore[assignment]
    app.agent.read_documents = [str(path), str(copy)]

    await app._ingest_read_documents()  # noqa: SLF001

    assert later.id is not None
    assert user.id is not None
    assert get_documents_by_message(db, later.id) == []
    assert len(get_documents_by_message(db, user.id)) == 1


@pytest.mark.asyncio
async def test_ingest_read_documents_skips_a_file_that_is_gone(
    db: Database, profile_id: int, tmp_path: Path
) -> None:
    app, user = _app(db, profile_id, [str(tmp_path / "missing.md")])

    await app._ingest_read_documents()  # noqa: SLF001

    assert user.id is not None
    assert get_documents_by_message(db, user.id) == []
