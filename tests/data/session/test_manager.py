"""Tests for the ``sensai.data.session.manager`` module."""

import re

import pytest

from sensai.data.database.database import Database
from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import Profile
from sensai.data.session.manager import (
    HISTORY_CONTEXT_NOTE,
    SessionManager,
    add_message_to_current_session,
    build_messages,
    clear_current_session,
    compress_session,
    create_new_session,
    get_current_session,
    get_current_session_id,
    is_current_session,
    maybe_compress_session,
    set_current_session,
    update_session,
)
from sensai.data.session.message import Message as SessionMessage
from sensai.data.session.message import create_message
from sensai.data.session.session import Session, create_session, get_session, set_session_summary
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
        {"role": "system", "content": HISTORY_CONTEXT_NOTE},
        {"role": "user", "content": "what did I just say?"},
    ]


def test_build_messages_prefixes_a_summary_as_a_system_message() -> None:
    session = Session(profile_id=1, id=1, summary="the user said hi")

    messages = build_messages(session, "what did I say?")

    assert messages == [
        {"role": "system", "content": "Conversation summary so far: the user said hi"},
        {"role": "system", "content": HISTORY_CONTEXT_NOTE},
        {"role": "user", "content": "what did I say?"},
    ]


def test_build_messages_omits_messages_already_folded_into_the_summary() -> None:
    session = Session(
        profile_id=1,
        id=1,
        summary="the user said hi",
        summarized_message_id=1,
        messages=[
            SessionMessage(id=1, session_id=1, content="hi", role="user", response_time=1.0),
            SessionMessage(
                id=2, session_id=1, content="how are you?", role="user", response_time=2.0
            ),
        ],
    )

    messages = build_messages(session, "still there?")

    assert messages == [
        {"role": "system", "content": "Conversation summary so far: the user said hi"},
        {"role": "user", "content": "how are you?"},
        {"role": "system", "content": HISTORY_CONTEXT_NOTE},
        {"role": "user", "content": "still there?"},
    ]


def test_build_messages_prefixes_the_current_profiles_preferences_and_instructions() -> None:
    session = Session(profile_id=1, id=1)
    ProfileManager.current_profile = Profile(
        name="Ada",
        password="hashed",  # noqa: S106
        id=1,
        preferences="dark mode",
        instructions="be concise",
    )

    messages = build_messages(session, "hello")

    assert messages == [
        {
            "role": "system",
            "content": "User preferences: dark mode\nInstructions (YOU MUST FOLLOW): be concise",
        },
        {"role": "user", "content": "hello"},
    ]


def test_build_messages_omits_profile_context_without_a_current_profile() -> None:
    session = Session(profile_id=1, id=1)
    ProfileManager.current_profile = None

    messages = build_messages(session, "hello")

    assert messages == [{"role": "user", "content": "hello"}]


def test_build_messages_omits_profile_context_when_it_does_not_own_the_session() -> None:
    session = Session(profile_id=1, id=1)
    ProfileManager.current_profile = Profile(
        name="Ada",
        password="hashed",  # noqa: S106
        id=2,
        preferences="dark mode",
    )

    messages = build_messages(session, "hello")

    assert messages == [{"role": "user", "content": "hello"}]


def test_build_messages_omits_profile_context_when_profile_has_neither_field_set() -> None:
    session = Session(profile_id=1, id=1)
    ProfileManager.current_profile = Profile(name="Ada", password="hashed", id=1)  # noqa: S106

    messages = build_messages(session, "hello")

    assert messages == [{"role": "user", "content": "hello"}]


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


def test_add_message_to_current_session_persists_it(db: Database, profile_id: int) -> None:
    session = create_new_session(db, profile_id)
    assert session.id is not None

    add_message_to_current_session(db, "hello", "user", 1.0)

    fetched = get_session(db, session.id)
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


def test_update_session_persists_to_the_passed_session_not_the_global_current(
    db: Database, profile_id: int
) -> None:
    other_session = create_new_session(db, profile_id, "other")
    assert get_current_session() is other_session
    target_session = create_session(db, profile_id, "target")
    assert target_session.id is not None
    response = _make_response(messages=[Message(role="user", content="hi", response_time=1.0)])

    result = update_session(db, target_session, response)

    assert result is not None
    assert result.id == target_session.id
    assert [m.content for m in result.messages] == ["hi"]
    other_after = get_session(db, other_session.id)  # type: ignore[arg-type]
    assert other_after is not None
    assert other_after.messages == []


def test_update_session_uses_the_given_sent_prefix_length_over_recomputing_it(
    db: Database, profile_id: int
) -> None:
    session = create_new_session(db, profile_id)
    # Simulate state (e.g. a preference) that changed after build_messages() ran but before
    # update_session() was called: recomputing the prefix length now would disagree with
    # what was actually sent, so the caller must be able to pin it down explicitly.
    response = _make_response(
        messages=[
            Message(role="system", content="a context line", response_time=1.0),
            Message(role="user", content="hi", response_time=1.0),
            Message(role="assistant", content="hello!", response_time=2.0),
        ]
    )

    result = update_session(db, session, response, sent_prefix_length=1)

    assert result is not None
    assert [m.content for m in result.messages] == ["hi", "hello!"]


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

    # A response built with build_messages() echoes the whole history back (plus the
    # history-context note), then the new turn: the first three messages here are
    # already persisted from first_turn or synthetic.
    second_turn = _make_response(
        messages=[
            Message(role="user", content="hi", response_time=1.0),
            Message(role="assistant", content="hello!", response_time=2.0),
            Message(role="system", content=HISTORY_CONTEXT_NOTE, response_time=3.0),
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


def test_update_session_skips_the_summary_line_when_persisting(
    db: Database, profile_id: int
) -> None:
    session: Session | None = create_new_session(db, profile_id)
    assert session is not None
    assert session.id is not None
    create_message(db, session.id, "hi", "user", 1.0)
    last_summarized = create_message(db, session.id, "hello!", "assistant", 2.0)
    assert last_summarized.id is not None
    set_session_summary(db, session.id, "the user said hi and got a greeting", last_summarized.id)
    session = get_session(db, session.id)
    assert session is not None

    # build_messages() would have sent [summary system message, history-context note, new
    # prompt] for this turn, since both prior messages are already folded into the summary.
    response = _make_response(
        messages=[
            Message(role="system", content="Conversation summary so far: ...", response_time=3.0),
            Message(role="system", content=HISTORY_CONTEXT_NOTE, response_time=3.0),
            Message(role="user", content="still there?", response_time=3.0),
            Message(role="assistant", content="yep!", response_time=4.0),
        ]
    )

    result = update_session(db, session, response)

    assert result is not None
    assert [m.content for m in result.messages] == ["hi", "hello!", "still there?", "yep!"]
    assert [m.role for m in result.messages] == ["user", "assistant", "user", "assistant"]


def test_update_session_skips_the_profile_context_line_when_persisting(
    db: Database, profile_id: int
) -> None:
    session = create_new_session(db, profile_id)
    ProfileManager.current_profile = Profile(
        name="Ada",
        password="hashed",  # noqa: S106
        id=profile_id,
        preferences="dark mode",
    )

    # build_messages() would have sent [profile context system message, new prompt] for this
    # first turn, since there's no history yet.
    response = _make_response(
        messages=[
            Message(role="system", content="User preferences: dark mode", response_time=1.0),
            Message(role="user", content="hi", response_time=1.0),
            Message(role="assistant", content="hello!", response_time=2.0),
        ]
    )

    result = update_session(db, session, response)

    assert result is not None
    assert [m.content for m in result.messages] == ["hi", "hello!"]
    assert [m.role for m in result.messages] == ["user", "assistant"]

    # Calling build_messages() again for a second turn must not see the profile line as
    # part of the persisted history either, so it can't compound into further duplicates.
    second_messages = build_messages(result, "still there?")
    assert second_messages == [
        {"role": "system", "content": "User preferences: dark mode"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello!"},
        {"role": "system", "content": HISTORY_CONTEXT_NOTE},
        {"role": "user", "content": "still there?"},
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


def test_compress_session_returns_unchanged_when_there_is_no_history(
    db: Database, profile_id: int
) -> None:
    session = create_new_session(db, profile_id)

    result = compress_session(db, session)

    assert result is session


def test_compress_session_raises_without_a_session_id(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id)
    session.id = None

    with pytest.raises(ValueError, match=re.escape("Session does not have a valid ID.")):
        compress_session(db, session)


def test_compress_session_folds_history_into_a_summary(
    db: Database, profile_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session: Session | None = create_new_session(db, profile_id)
    assert session is not None
    assert session.id is not None
    create_message(db, session.id, "hi", "user", 1.0)
    last_message = create_message(db, session.id, "hello!", "assistant", 2.0)
    assert last_message.id is not None
    session = get_session(db, session.id)
    assert session is not None

    captured_prompts: list[str] = []

    def fake_get_sensei_response(prompt: str | None = None, **_kwargs: object) -> Response:
        assert prompt is not None
        captured_prompts.append(prompt)
        return _make_response()

    monkeypatch.setattr("sensai.data.session.manager.get_sensei_response", fake_get_sensei_response)

    result = compress_session(db, session)

    assert result.summary == "hi"
    assert result.summarized_message_id == last_message.id
    assert "user: hi" in captured_prompts[0]
    assert "assistant: hello!" in captured_prompts[0]


def test_compress_session_summarizes_with_the_given_model(
    db: Database, profile_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session: Session | None = create_new_session(db, profile_id)
    assert session is not None
    assert session.id is not None
    create_message(db, session.id, "hi", "user", 1.0)
    session = get_session(db, session.id)
    assert session is not None

    captured: dict[str, object] = {}

    def fake_get_sensei_response(prompt: str | None = None, **kwargs: object) -> Response:
        captured.update(kwargs)
        return _make_response()

    monkeypatch.setattr("sensai.data.session.manager.get_sensei_response", fake_get_sensei_response)

    compress_session(db, session, model="mistral")

    assert captured["model"] == "mistral"


def test_maybe_compress_session_summarizes_with_the_responses_model(
    db: Database, profile_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session: Session | None = create_new_session(db, profile_id)
    assert session is not None
    assert session.id is not None
    create_message(db, session.id, "hi", "user", 1.0)
    session = get_session(db, session.id)
    assert session is not None
    response = _make_response(prompt_eval_count=5000)
    response.model = "mistral"

    captured: dict[str, object] = {}

    def fake_get_sensei_response(prompt: str | None = None, **kwargs: object) -> Response:
        captured.update(kwargs)
        return _make_response()

    monkeypatch.setattr("sensai.data.session.manager.get_sensei_response", fake_get_sensei_response)

    maybe_compress_session(db, session, response, threshold=3000)

    assert captured["model"] == "mistral"


def test_compress_session_only_folds_in_history_not_already_summarized(
    db: Database, profile_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session: Session | None = create_new_session(db, profile_id)
    assert session is not None
    assert session.id is not None
    first_message = create_message(db, session.id, "hi", "user", 1.0)
    assert first_message.id is not None
    set_session_summary(db, session.id, "the user said hi", first_message.id)
    second_message = create_message(db, session.id, "how are you?", "user", 2.0)
    assert second_message.id is not None
    session = get_session(db, session.id)
    assert session is not None

    captured_prompts: list[str] = []

    def fake_get_sensei_response(prompt: str | None = None, **_kwargs: object) -> Response:
        assert prompt is not None
        captured_prompts.append(prompt)
        return _make_response()

    monkeypatch.setattr("sensai.data.session.manager.get_sensei_response", fake_get_sensei_response)

    result = compress_session(db, session)

    assert result.summarized_message_id == second_message.id
    new_conversation_section = captured_prompts[0].split("New conversation to fold in:")[1]
    assert "the user said hi" in captured_prompts[0]
    assert "user: hi" not in new_conversation_section
    assert "how are you?" in new_conversation_section


def test_maybe_compress_session_skips_when_under_threshold(db: Database, profile_id: int) -> None:
    session = create_new_session(db, profile_id)
    response = _make_response(prompt_eval_count=100)

    result = maybe_compress_session(db, session, response, threshold=3000)

    assert result is session


def test_maybe_compress_session_compresses_when_over_threshold(
    db: Database, profile_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session: Session | None = create_new_session(db, profile_id)
    assert session is not None
    assert session.id is not None
    last_message = create_message(db, session.id, "hi", "user", 1.0)
    assert last_message.id is not None
    session = get_session(db, session.id)
    assert session is not None
    response = _make_response(prompt_eval_count=5000)

    monkeypatch.setattr(
        "sensai.data.session.manager.get_sensei_response",
        lambda *args, **kwargs: _make_response(),
    )

    result = maybe_compress_session(db, session, response, threshold=3000)

    assert result.summary == "hi"
    assert result.summarized_message_id == last_message.id
