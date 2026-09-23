"""Tests for the ``sensai.data.session.manager`` module."""

import re

import pytest

from sensai.data.database.database import Database
from sensai.data.session.manager import (
    SessionManager,
    add_message_to_current_session,
    build_messages,
    clear_current_session,
    create_new_session,
    get_current_session,
    get_current_session_id,
    get_session_by_id,
    is_current_session,
    set_current_session,
    update_session,
)
from sensai.data.session.message import Message as SessionMessage
from sensai.data.session.session import Session, create_session
from sensai.requester import Message, Response


def test_build_messages_with_no_history_returns_just_the_prompt() -> None:
    session = Session(profile_id=1, id=1)

    messages = build_messages(session, "hello")

    assert messages == [{"role": "user", "content": "hello"}]


def test_build_messages_prefixes_session_history_before_the_prompt() -> None:
    session = Session(
        profile_id=1,
        id=1,
        messages=[
            SessionMessage(session_id=1, content="hi", role="user", response_time=1.0),
            SessionMessage(session_id=1, content="hello!", role="assistant", response_time=2.0),
        ],
    )

    messages = build_messages(session, "what did I just say?")

    assert messages == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello!"},
        {"role": "user", "content": "what did I just say?"},
    ]


def _make_response(
    messages: list[Message] | None = None,
    prompt_eval_count: int = 0,
    eval_count: int = 0,
    token_used: int = 0,
) -> Response:
    return Response(
        response="hi",
        respond_time=2.0,
        request_time=1.0,
        total_duration=0,
        model="llama3.2",
        tools=[],
        messages=messages or [],
        prompt_eval_count=prompt_eval_count,
        eval_count=eval_count,
        token_used=token_used,
        status_code=200,
        tool_calls=[],
        stop_reason="stop",
    )


def test_get_current_session_is_none_by_default() -> None:
    assert get_current_session() is None


def test_set_and_get_current_session(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id)

    set_current_session(session)

    assert get_current_session() is session


def test_clear_current_session(db: Database, profile_id: int) -> None:
    set_current_session(create_session(db, profile_id))

    clear_current_session()

    assert get_current_session() is None


def test_create_new_session_sets_it_as_current(db: Database, profile_id: int) -> None:
    session = create_new_session(db, profile_id, "test session")

    assert session.name == "test session"
    assert get_current_session() is session


def test_get_current_session_id_is_none_without_a_session() -> None:
    assert get_current_session_id() is None


def test_get_current_session_id_matches_the_current_session(db: Database, profile_id: int) -> None:
    session = create_new_session(db, profile_id)

    assert get_current_session_id() == session.id


def test_is_current_session_true_for_the_current_session(db: Database, profile_id: int) -> None:
    session = create_new_session(db, profile_id)
    assert session.id is not None

    assert is_current_session(session.id) is True


def test_is_current_session_false_for_another_session(db: Database, profile_id: int) -> None:
    create_new_session(db, profile_id)

    assert is_current_session(9999) is False


def test_is_current_session_false_without_a_current_session() -> None:
    assert is_current_session(1) is False


def test_get_session_by_id_delegates_to_get_session(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id)
    assert session.id is not None

    fetched = get_session_by_id(db, session.id)

    assert fetched is not None
    assert fetched.id == session.id


def test_add_message_to_current_session_persists_it(db: Database, profile_id: int) -> None:
    session = create_new_session(db, profile_id)
    assert session.id is not None

    add_message_to_current_session(db, "hello", "user", 1.0)

    fetched = get_session_by_id(db, session.id)
    assert fetched is not None
    assert [m.content for m in fetched.messages] == ["hello"]


def test_add_message_to_current_session_raises_without_a_current_session(db: Database) -> None:
    with pytest.raises(ValueError, match=re.escape("No current session is set.")):
        add_message_to_current_session(db, "hello", "user", 1.0)


def test_update_session_returns_none_when_session_has_no_id(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id)
    session.id = None

    result = update_session(db, session, _make_response())

    assert result is None


def test_update_session_persists_the_response_messages(db: Database, profile_id: int) -> None:
    session = create_new_session(db, profile_id)
    response = _make_response(
        messages=[
            Message(role="user", content="hi", response_time=1.0),
            Message(role="assistant", content="hello!", response_time=2.0),
        ]
    )

    result = update_session(db, session, response)

    assert result is not None
    assert [m.content for m in result.messages] == ["hi", "hello!"]
    assert [m.role for m in result.messages] == ["user", "assistant"]


def test_update_session_only_persists_messages_new_to_this_turn(
    db: Database, profile_id: int
) -> None:
    session: Session | None = create_new_session(db, profile_id)
    assert session is not None
    first_turn = _make_response(
        messages=[
            Message(role="user", content="hi", response_time=1.0),
            Message(role="assistant", content="hello!", response_time=2.0),
        ]
    )
    session = update_session(db, session, first_turn)
    assert session is not None

    # A response built with build_messages() echoes the whole history back, plus the
    # new turn: the first two messages here are already persisted from first_turn.
    second_turn = _make_response(
        messages=[
            Message(role="user", content="hi", response_time=1.0),
            Message(role="assistant", content="hello!", response_time=2.0),
            Message(role="user", content="what did I say?", response_time=3.0),
            Message(role="assistant", content="you said hi", response_time=4.0),
        ]
    )

    result = update_session(db, session, second_turn)

    assert result is not None
    assert [m.content for m in result.messages] == [
        "hi",
        "hello!",
        "what did I say?",
        "you said hi",
    ]


def test_update_session_accumulates_token_usage(db: Database, profile_id: int) -> None:
    session = create_new_session(db, profile_id)
    response = _make_response(prompt_eval_count=10, eval_count=4, token_used=14)

    result = update_session(db, session, response)

    assert result is not None
    assert result.prompt_eval_count == 10
    assert result.eval_count == 4
    assert result.token_used == 14


def test_current_session_state_is_shared_across_the_class(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id)
    set_current_session(session)

    assert SessionManager.current_session is session
