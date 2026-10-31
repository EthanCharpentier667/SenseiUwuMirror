"""Tests for the ``sensai.data.session.session`` module."""

import peewee
import pytest

from sensai.data.database.database import Database
from sensai.data.profile.profile import create_profile
from sensai.data.session.chunk import EMBEDDING_DIMENSIONS, Chunk, create_chunk
from sensai.data.session.document import create_document, get_document
from sensai.data.session.message import create_message, get_message
from sensai.data.session.session import (
    add_session_usage,
    create_session,
    delete_session,
    find_sessions_by_name,
    get_session,
    list_sessions,
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


def test_create_session_sets_last_updated(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id)

    assert session.last_updated is not None


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


def test_rename_session_updates_last_updated(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id, name="old name")
    assert session.id is not None
    assert session.last_updated is not None

    rename_session(db, session.id, "new name")

    updated = get_session(db, session.id)
    assert updated is not None
    assert updated.last_updated is not None
    assert updated.last_updated > session.last_updated


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


def test_list_sessions_puts_the_most_recently_used_first(db: Database, profile_id: int) -> None:
    older = create_session(db, profile_id, name="older")
    newer = create_session(db, profile_id, name="newer")
    assert older.id is not None
    rename_session(db, older.id, "older, used again")

    names = [session.name for session in list_sessions(db, profile_id)]

    assert names == ["older, used again", newer.name]


def test_list_sessions_counts_messages_without_loading_them(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id)
    create_session(db, profile_id)
    assert session.id is not None
    create_message(db, session.id, "hi", "user", 1.0)
    create_message(db, session.id, "hello", "assistant", 1.0)

    counts = {listed.id: listed.message_count for listed in list_sessions(db, profile_id)}

    assert counts[session.id] == 2
    assert sorted(counts.values()) == [0, 2]
    assert list_sessions(db, profile_id)[0].messages == []


def test_list_sessions_only_lists_the_profiles_own(db: Database, profile_id: int) -> None:
    other = create_profile(db, "Other", "secret").id
    assert other is not None
    create_session(db, other, name="not mine")
    mine = create_session(db, profile_id, name="mine")

    assert [session.id for session in list_sessions(db, profile_id)] == [mine.id]


def test_find_sessions_by_name_prefers_an_exact_match(db: Database, profile_id: int) -> None:
    exact = create_session(db, profile_id, name="Python")
    create_session(db, profile_id, name="Python help")

    assert [session.id for session in find_sessions_by_name(db, profile_id, "Python")] == [exact.id]


def test_find_sessions_by_name_falls_back_to_a_case_insensitive_prefix(
    db: Database, profile_id: int
) -> None:
    first = create_session(db, profile_id, name="Python help")
    second = create_session(db, profile_id, name="python tests")
    create_session(db, profile_id, name="Rust")
    create_session(db, profile_id)

    found = {session.id for session in find_sessions_by_name(db, profile_id, "PYTH")}

    assert found == {first.id, second.id}


def test_find_sessions_by_name_ignores_other_profiles(db: Database, profile_id: int) -> None:
    other = create_profile(db, "Other", "secret").id
    assert other is not None
    create_session(db, other, name="Python")

    assert find_sessions_by_name(db, profile_id, "Python") == []


def test_delete_session_removes_its_messages_documents_and_chunks(
    db: Database, profile_id: int
) -> None:
    session = create_session(db, profile_id)
    kept = create_session(db, profile_id)
    assert session.id is not None
    assert kept.id is not None
    message = create_message(db, session.id, "File: notes.md", "user", 0.0)
    kept_message = create_message(db, kept.id, "hi", "user", 0.0)
    assert message.id is not None
    document = create_document(db, message.id, b"notes")
    assert document.id is not None
    chunk = create_chunk(db, document.id, 0, "notes", [0.0] * EMBEDDING_DIMENSIONS)

    delete_session(db, session.id)

    assert get_session(db, session.id) is None
    assert get_message(db, message.id) is None
    assert get_document(db, document.id) is None
    with db.database.bind_ctx([Chunk]):
        assert Chunk.get_or_none(Chunk.id == chunk.id) is None
    assert kept_message.id is not None
    assert get_message(db, kept_message.id) is not None
