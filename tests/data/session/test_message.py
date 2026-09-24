"""Tests for the ``sensai.data.session.message`` module."""

import peewee
import pytest

from sensai.data.database.database import Database
from sensai.data.session.message import create_message, get_message, get_messages_by_session
from sensai.data.session.session import create_session


@pytest.fixture
def session_id(db: Database, profile_id: int) -> int:
    session = create_session(db, profile_id)
    assert session.id is not None
    return session.id


def test_create_message_assigns_an_id(db: Database, session_id: int) -> None:
    message = create_message(db, session_id, "hello", "user", 1.0)

    assert message.id is not None
    assert message.content == "hello"
    assert message.role == "user"
    assert message.response_time == 1.0
    assert message.session_id == session_id


def test_create_message_starts_with_no_documents(db: Database, session_id: int) -> None:
    message = create_message(db, session_id, "hello", "user", 1.0)

    assert message.documents == []


def test_create_message_rejects_unknown_session(db: Database) -> None:
    with pytest.raises(peewee.IntegrityError):
        create_message(db, 9999, "hello", "user", 1.0)


def test_get_message_returns_none_when_missing(db: Database) -> None:
    assert get_message(db, 9999) is None


def test_get_message_round_trips_a_created_message(db: Database, session_id: int) -> None:
    created = create_message(db, session_id, "hello", "assistant", 2.5)
    assert created.id is not None

    fetched = get_message(db, created.id)

    assert fetched is not None
    assert fetched.content == "hello"
    assert fetched.role == "assistant"
    assert fetched.response_time == 2.5


def test_get_messages_by_session_orders_oldest_first(db: Database, session_id: int) -> None:
    create_message(db, session_id, "first", "user", 1.0)
    create_message(db, session_id, "second", "assistant", 2.0)
    create_message(db, session_id, "third", "user", 3.0)

    messages = get_messages_by_session(db, session_id)

    assert [m.content for m in messages] == ["first", "second", "third"]


def test_get_messages_by_session_only_returns_matching_session(
    db: Database, profile_id: int, session_id: int
) -> None:
    other_session = create_session(db, profile_id)
    assert other_session.id is not None
    create_message(db, session_id, "mine", "user", 1.0)
    create_message(db, other_session.id, "not mine", "user", 1.0)

    messages = get_messages_by_session(db, session_id)

    assert [m.content for m in messages] == ["mine"]


def test_get_messages_by_session_returns_empty_list_when_none(
    db: Database, session_id: int
) -> None:
    assert get_messages_by_session(db, session_id) == []
