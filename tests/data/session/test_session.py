"""Tests for the ``sensai.data.session.session`` module."""

import peewee
import pytest

from sensai.data.database.database import Database
from sensai.data.profile.profile import create_profile
from sensai.data.session.message import create_message
from sensai.data.session.session import (
    add_session_usage,
    create_session,
    get_session,
    rename_session,
    set_session_summary,
)


def test_create_session_assigns_an_id(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id, name="My chat")

    assert session.id is not None
    assert session.name == "My chat"
    assert session.profile_id == profile_id


def test_create_session_without_name_defaults_to_none(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id)

    assert session.name is None


def test_create_session_starts_with_zeroed_usage_and_no_messages(
    db: Database, profile_id: int
) -> None:
    session = create_session(db, profile_id)

    assert session.prompt_eval_count == 0
    assert session.eval_count == 0
    assert session.token_used == 0
    assert session.summary is None
    assert session.summarized_message_id is None
    assert session.messages == []


def test_create_session_rejects_unknown_profile(db: Database) -> None:
    with pytest.raises(peewee.IntegrityError):
        create_session(db, profile_id=9999, name="orphan")


def test_get_session_returns_none_when_missing(db: Database) -> None:
    assert get_session(db, 9999) is None


def test_get_session_round_trips_a_created_session(db: Database, profile_id: int) -> None:
    created = create_session(db, profile_id, name="My chat")
    assert created.id is not None

    fetched = get_session(db, created.id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == "My chat"
    assert fetched.profile_id == profile_id


def test_get_session_includes_its_messages(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id)
    assert session.id is not None
    create_message(db, session.id, "hi", "user", 1.0)
    create_message(db, session.id, "hello!", "assistant", 2.0)

    fetched = get_session(db, session.id)

    assert fetched is not None
    assert [m.content for m in fetched.messages] == ["hi", "hello!"]


def test_rename_session_changes_the_name(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id, name="old name")
    assert session.id is not None

    rename_session(db, session.id, "new name")

    updated = get_session(db, session.id)
    assert updated is not None
    assert updated.name == "new name"


def test_add_session_usage_accumulates_across_calls(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id)
    assert session.id is not None

    add_session_usage(db, session.id, prompt_eval_count=10, eval_count=5, token_used=15)
    add_session_usage(db, session.id, prompt_eval_count=3, eval_count=2, token_used=5)

    updated = get_session(db, session.id)
    assert updated is not None
    assert updated.prompt_eval_count == 13
    assert updated.eval_count == 7
    assert updated.token_used == 20


def test_set_session_summary_persists_summary_and_cutoff(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id)
    assert session.id is not None
    message = create_message(db, session.id, "hi", "user", 1.0)
    assert message.id is not None

    set_session_summary(db, session.id, "the user said hi", message.id)

    updated = get_session(db, session.id)
    assert updated is not None
    assert updated.summary == "the user said hi"
    assert updated.summarized_message_id == message.id


def test_set_session_summary_overwrites_a_previous_summary(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id)
    assert session.id is not None
    first_message = create_message(db, session.id, "hi", "user", 1.0)
    second_message = create_message(db, session.id, "how are you?", "user", 2.0)
    assert first_message.id is not None
    assert second_message.id is not None
    set_session_summary(db, session.id, "the user said hi", first_message.id)

    set_session_summary(db, session.id, "the user greeted and asked how I am", second_message.id)

    updated = get_session(db, session.id)
    assert updated is not None
    assert updated.summary == "the user greeted and asked how I am"
    assert updated.summarized_message_id == second_message.id


def test_sessions_are_isolated_by_profile(db: Database) -> None:
    profile_a = create_profile(db, "A", "secret").id
    profile_b = create_profile(db, "B", "secret").id
    assert profile_a is not None
    assert profile_b is not None

    session = create_session(db, profile_a)

    assert session.profile_id == profile_a
    assert session.profile_id != profile_b
