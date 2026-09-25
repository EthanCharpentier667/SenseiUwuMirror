"""Tests for the ``sensai.data.session.document`` module."""

import peewee
import pytest

from sensai.data.database.database import Database
from sensai.data.session.document import create_document, get_document, get_documents_by_message
from sensai.data.session.message import create_message
from sensai.data.session.session import create_session


@pytest.fixture
def message_id(db: Database, profile_id: int) -> int:
    session = create_session(db, profile_id)
    assert session.id is not None
    message = create_message(db, session.id, "hi", "user", 1.0)
    assert message.id is not None
    return message.id


def test_create_document_assigns_an_id(db: Database, message_id: int) -> None:
    document = create_document(db, message_id, b"raw bytes")

    assert document.id is not None
    assert document.content == b"raw bytes"
    assert document.message_id == message_id


def test_create_document_rejects_unknown_message(db: Database) -> None:
    with pytest.raises(peewee.IntegrityError):
        create_document(db, 9999, b"raw bytes")


def test_get_document_returns_none_when_missing(db: Database) -> None:
    assert get_document(db, 9999) is None


def test_get_document_round_trips_binary_content(db: Database, message_id: int) -> None:
    created = create_document(db, message_id, b"\x00\x01\x02binary")
    assert created.id is not None

    fetched = get_document(db, created.id)

    assert fetched is not None
    assert fetched.content == b"\x00\x01\x02binary"


def test_get_documents_by_message_returns_all_attached_documents(
    db: Database, message_id: int
) -> None:
    create_document(db, message_id, b"first")
    create_document(db, message_id, b"second")

    documents = get_documents_by_message(db, message_id)

    assert [d.content for d in documents] == [b"first", b"second"]


def test_get_documents_by_message_only_returns_matching_message(
    db: Database, profile_id: int, message_id: int
) -> None:
    session = create_session(db, profile_id)
    assert session.id is not None
    other_message = create_message(db, session.id, "other", "user", 1.0)
    assert other_message.id is not None

    create_document(db, message_id, b"mine")
    create_document(db, other_message.id, b"not mine")

    documents = get_documents_by_message(db, message_id)

    assert [d.content for d in documents] == [b"mine"]


def test_get_documents_by_message_returns_empty_list_when_none(
    db: Database, message_id: int
) -> None:
    assert get_documents_by_message(db, message_id) == []
