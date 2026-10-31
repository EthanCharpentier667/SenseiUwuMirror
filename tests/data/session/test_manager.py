"""Tests for the ``sensai.data.session.manager`` module."""

import re
from typing import Any

import pytest

from sensai.client import OllamaClient, Response
from sensai.data.database.database import Database
from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import Profile
from sensai.data.session.chunk import EMBEDDING_DIMENSIONS, Chunk, create_chunk
from sensai.data.session.document import create_document
from sensai.data.session.manager import (
    HISTORY_CONTEXT_NOTE,
    RETRIEVED_CONTEXT_NOTE,
    CompressionRejectedError,
    SessionManager,
    add_message_to_current_session,
    build_messages,
    clear_current_session,
    compress_session,
    create_new_session,
    ensure_persisted,
    generate_session_title,
    get_current_session,
    get_current_session_id,
    is_current_session,
    maybe_compress_session,
    new_session,
    retrieve_chunks,
    set_current_session,
    update_session,
)
from sensai.data.session.message import Message, create_message
from sensai.data.session.message import Message as SessionMessage
from sensai.data.session.session import (
    Session,
    create_session,
    get_session,
    rename_session,
    set_session_summary,
)
from sensai.features.rag.embedder import Embedder

TEST_BASE_URL = "http://localhost:11434/api/chat"
TEST_TOKEN = "test-token"  # noqa: S105
TEST_TIMEOUT = 30.0


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


@pytest.mark.asyncio
async def test_compress_session_returns_unchanged_when_there_is_no_history(
    db: Database, profile_id: int
) -> None:
    session = create_new_session(db, profile_id)
    client = OllamaClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)

    result = await compress_session(db, session, client)

    assert result is session


@pytest.mark.asyncio
async def test_compress_session_raises_without_a_session_id(db: Database, profile_id: int) -> None:
    session = create_session(db, profile_id)
    session.id = None
    client = OllamaClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)

    with pytest.raises(ValueError, match=re.escape("Session does not have a valid ID.")):
        await compress_session(db, session, client)


@pytest.mark.asyncio
async def test_compress_session_folds_history_into_a_summary(
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

    async def fake_chat(
        _self: OllamaClient, messages: list[dict[str, str]], **_kwargs: object
    ) -> Response:
        prompt = messages[0]["content"]
        captured_prompts.append(prompt)
        return _make_response()

    monkeypatch.setattr(OllamaClient, "chat", fake_chat)
    client = OllamaClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)

    result = await compress_session(db, session, client)

    assert result.summary == "hi"
    assert result.summarized_message_id == last_message.id
    assert "user: hi" in captured_prompts[0]
    assert "assistant: hello!" in captured_prompts[0]


@pytest.mark.asyncio
async def test_compress_session_summarizes_with_the_given_model(
    db: Database, profile_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session: Session | None = create_new_session(db, profile_id)
    assert session is not None
    assert session.id is not None
    create_message(db, session.id, "hello there", "user", 1.0)
    session = get_session(db, session.id)
    assert session is not None

    captured: dict[str, object] = {}

    async def fake_chat(_self: OllamaClient, **kwargs: object) -> Response:
        captured.update(kwargs)
        return _make_response()

    monkeypatch.setattr(OllamaClient, "chat", fake_chat)
    client = OllamaClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)

    await compress_session(db, session, client, model="mistral")

    assert captured["model"] == "mistral"


@pytest.mark.asyncio
async def test_maybe_compress_session_summarizes_with_the_given_model(
    db: Database, profile_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session: Session | None = create_new_session(db, profile_id)
    assert session is not None
    assert session.id is not None
    create_message(db, session.id, "hi", "user", 1.0)
    session = get_session(db, session.id)
    assert session is not None
    captured: dict[str, object] = {}

    async def fake_chat(_self: OllamaClient, **kwargs: object) -> Response:
        captured.update(kwargs)
        return _make_response()

    monkeypatch.setattr(OllamaClient, "chat", fake_chat)
    client = OllamaClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)

    await maybe_compress_session(db, session, 5000, threshold=3000, client=client, model="mistral")

    assert captured["model"] == "mistral"


@pytest.mark.asyncio
async def test_compress_session_only_folds_in_history_not_already_summarized(
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

    async def fake_chat(
        _self: OllamaClient, messages: list[dict[str, str]], **_kwargs: object
    ) -> Response:
        prompt = messages[0]["content"]
        captured_prompts.append(prompt)
        return _make_response()

    monkeypatch.setattr(OllamaClient, "chat", fake_chat)
    client = OllamaClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)

    result = await compress_session(db, session, client)

    assert result.summarized_message_id == second_message.id
    new_conversation_section = captured_prompts[0].split("New conversation to fold in:")[1]
    assert "the user said hi" in captured_prompts[0]
    assert "user: hi" not in new_conversation_section
    assert "how are you?" in new_conversation_section


@pytest.mark.asyncio
async def test_maybe_compress_session_skips_when_under_threshold(
    db: Database, profile_id: int
) -> None:
    session = create_new_session(db, profile_id)
    client = OllamaClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)

    result = await maybe_compress_session(db, session, 100, threshold=3000, client=client)

    assert result is session


@pytest.mark.asyncio
async def test_maybe_compress_session_compresses_when_over_threshold(
    db: Database, profile_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session: Session | None = create_new_session(db, profile_id)
    assert session is not None
    assert session.id is not None
    last_message = create_message(db, session.id, "hello there", "user", 1.0)
    assert last_message.id is not None
    session = get_session(db, session.id)
    assert session is not None

    async def fake_chat(_self: OllamaClient, *args: object, **kwargs: object) -> Response:
        return _make_response()

    monkeypatch.setattr(OllamaClient, "chat", fake_chat)
    client = OllamaClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)

    result = await maybe_compress_session(db, session, 5000, threshold=3000, client=client)

    assert result.summary == "hi"
    assert result.summarized_message_id == last_message.id


class _SummaryClient(OllamaClient):
    """Client answering every chat with a fixed summary, or failing, and counting the calls."""

    def __init__(self, summary: str | Exception = "short summary") -> None:
        """Initialize _SummaryClient with its answer."""
        super().__init__(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)
        self.summary = summary
        self.prompts: list[str] = []
        self.options: list[object] = []

    async def chat(self, **kwargs: Any) -> Response:  # type: ignore[override]
        self.prompts.append(kwargs["messages"][0]["content"])
        self.options.append(kwargs.get("options"))
        if isinstance(self.summary, Exception):
            raise self.summary
        response = _make_response()
        response.response = self.summary
        return response


class _ErrorUI:
    """UI recording the errors it's told about."""

    def __init__(self) -> None:
        """Initialize _ErrorUI without errors."""
        self.errors: list[str] = []

    async def start_spinner(self, _message: str) -> None:
        pass

    async def stop_spinner(self) -> None:
        pass

    async def on_error(self, error: Exception | str, *, title: str = "Error") -> None:
        self.errors.append(f"{title}: {error}")


def _long_session(db: Database, profile_id: int, *contents: tuple[str, str]) -> Session:
    created = create_session(db, profile_id)
    assert created.id is not None
    for index, (role, content) in enumerate(contents):
        create_message(db, created.id, content, role, float(index))
    session = get_session(db, created.id)
    assert session is not None
    return session


FOUR_EXCHANGES = (
    ("user", "first question about the cart"),
    ("assistant", "first answer about the cart"),
    ("user", "second question about the cart"),
    ("assistant", "second answer about the cart"),
    ("user", "third question about the cart"),
    ("assistant", "third answer about the cart"),
    ("user", "fourth question about the cart"),
    ("assistant", "fourth answer about the cart"),
)


@pytest.mark.asyncio
async def test_compress_session_keeps_the_latest_exchanges_word_for_word(
    db: Database, profile_id: int
) -> None:
    session = _long_session(db, profile_id, *FOUR_EXCHANGES)
    client = _SummaryClient()

    result = await compress_session(db, session, client, keep_turns=2)

    assert "second answer" in client.prompts[0]
    assert "third question" not in client.prompts[0]
    assert build_messages(result, "next")[0] == {
        "role": "system",
        "content": "Conversation summary so far: short summary",
    }
    assert [m["content"] for m in build_messages(result, "next") if m["role"] != "system"] == [
        "third question about the cart",
        "third answer about the cart",
        "fourth question about the cart",
        "fourth answer about the cart",
        "next",
    ]


@pytest.mark.asyncio
async def test_a_short_session_is_not_sent_to_the_model(db: Database, profile_id: int) -> None:
    session = _long_session(db, profile_id, *FOUR_EXCHANGES[:4])
    client = _SummaryClient()

    result = await maybe_compress_session(
        db, session, 5000, threshold=3000, client=client, keep_turns=2
    )

    assert result is session
    assert client.prompts == []


@pytest.mark.asyncio
async def test_attached_files_stay_with_the_exchange_they_lead_to(
    db: Database, profile_id: int
) -> None:
    session = _long_session(
        db,
        profile_id,
        ("user", "first question about the cart"),
        ("assistant", "first answer about the cart"),
        ("user", "File: cart-spec.md"),
        ("user", "second question about the cart"),
        ("assistant", "second answer about the cart"),
    )
    client = _SummaryClient()

    result = await compress_session(db, session, client, keep_turns=1)

    assert "File: cart-spec.md" not in client.prompts[0]
    kept = [m["content"] for m in build_messages(result, "next") if m["role"] != "system"]
    assert kept[:2] == ["File: cart-spec.md", "second question about the cart"]


@pytest.mark.asyncio
async def test_compress_session_summarizes_at_temperature_zero(
    db: Database, profile_id: int
) -> None:
    session = _long_session(db, profile_id, *FOUR_EXCHANGES)
    client = _SummaryClient()

    await compress_session(db, session, client)

    assert client.options == [{"temperature": 0}]


@pytest.mark.asyncio
@pytest.mark.parametrize("summary", ["", "   \n", "x" * 1000])
async def test_compress_session_rejects_an_unusable_summary(
    db: Database, profile_id: int, summary: str
) -> None:
    session = _long_session(db, profile_id, *FOUR_EXCHANGES)
    assert session.id is not None

    with pytest.raises(CompressionRejectedError):
        await compress_session(db, session, _SummaryClient(summary))

    unchanged = get_session(db, session.id)
    assert unchanged is not None
    assert unchanged.summary is None
    assert unchanged.summarized_message_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("summary", ["", RuntimeError("model down")])
async def test_a_failed_compression_is_reported_and_keeps_the_history(
    db: Database, profile_id: int, summary: str | Exception
) -> None:
    session = _long_session(db, profile_id, *FOUR_EXCHANGES)
    ui = _ErrorUI()

    result = await maybe_compress_session(
        db,
        session,
        5000,
        threshold=3000,
        client=_SummaryClient(summary),
        ui_handler=ui,  # type: ignore[arg-type]
    )

    assert result is session
    assert len(ui.errors) == 1
    assert ui.errors[0].startswith("Compression skipped: History kept as is")
    assert "first question about the cart" in [m["content"] for m in build_messages(result, "next")]


def _unit_vector(dimension: int) -> list[float]:
    return [1.0 if i == dimension else 0.0 for i in range(EMBEDDING_DIMENSIONS)]


class EmbedClient(OllamaClient):
    """Ollama client embedding every input as the same fixed vector, recording requests."""

    def __init__(self, vector: list[float]) -> None:
        """Initialize EmbedClient with the vector to answer."""
        super().__init__(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)
        self.vector = vector
        self.requests: list[list[str]] = []

    async def embed(self, inputs: list[str], model: str) -> list[list[float]]:  # noqa: ARG002
        self.requests.append(inputs)
        return [self.vector for _ in inputs]


def test_build_messages_places_retrieved_chunks_right_before_the_prompt() -> None:
    session = Session(
        profile_id=1,
        id=1,
        messages=[SessionMessage(session_id=1, content="hi", role="user", response_time=1.0)],
    )
    retrieved = [
        Chunk(document_id=7, position=2, content="Le serveur redémarre à minuit."),
        Chunk(document_id=8, position=0, content="Le café est en salle 3."),
    ]

    messages = build_messages(session, "quand redémarre le serveur ?", retrieved)

    assert messages[:-2] == [
        {"role": "user", "content": "hi"},
        {"role": "system", "content": HISTORY_CONTEXT_NOTE},
    ]
    assert messages[-2] == {
        "role": "system",
        "content": f"{RETRIEVED_CONTEXT_NOTE}\n\n"
        "[Document 7, excerpt 3]\nLe serveur redémarre à minuit.\n\n"
        "[Document 8, excerpt 1]\nLe café est en salle 3.",
    }
    assert messages[-1] == {"role": "user", "content": "quand redémarre le serveur ?"}


def test_build_messages_without_retrieved_chunks_adds_nothing() -> None:
    session = Session(profile_id=1, id=1)

    assert build_messages(session, "hello", []) == [{"role": "user", "content": "hello"}]


@pytest.mark.asyncio
async def test_retrieve_chunks_without_documents_does_not_embed(
    db: Database, profile_id: int
) -> None:
    session = create_session(db, profile_id)
    client = EmbedClient(_unit_vector(0))

    assert await retrieve_chunks(db, Embedder(client), session, "hello") == []
    assert client.requests == []


@pytest.mark.asyncio
async def test_retrieve_chunks_only_searches_the_sessions_documents(
    db: Database, profile_id: int
) -> None:
    session = create_session(db, profile_id)
    other_session = create_session(db, profile_id)
    assert session.id is not None
    assert other_session.id is not None
    message = create_message(db, session.id, "voici le doc", "user", 1.0)
    other_message = create_message(db, other_session.id, "autre doc", "user", 1.0)
    assert message.id is not None
    assert other_message.id is not None
    document = create_document(db, message.id, b"doc")
    other_document = create_document(db, other_message.id, b"other")
    assert document.id is not None
    assert other_document.id is not None
    create_chunk(db, document.id, 0, "proche", _unit_vector(0))
    create_chunk(db, document.id, 1, "loin", _unit_vector(1))
    create_chunk(db, other_document.id, 0, "autre session", _unit_vector(0))
    client = EmbedClient(_unit_vector(0))

    chunks = await retrieve_chunks(db, Embedder(client), session, "question", k=1)

    assert [chunk.content for chunk in chunks] == ["proche"]
    assert client.requests == [["search_query: question"]]


def test_update_session_persists_tool_messages_as_a_trace(db: Database, profile_id: int) -> None:
    session = create_new_session(db, profile_id)
    response = _make_response(
        messages=[
            Message(role="user", content="run the tests", response_time=1.0),
            Message(role="tool", content='{"tool": "bash", "status": "done"}', response_time=1.5),
            Message(role="assistant", content="All tests pass.", response_time=2.0),
        ]
    )

    result = update_session(db, session, response)

    assert result is not None
    assert [m.role for m in result.messages] == ["user", "tool", "assistant"]


def test_build_messages_never_sends_tool_messages_back() -> None:
    session = Session(
        profile_id=1,
        messages=[
            SessionMessage(session_id=1, content="run the tests", role="user", response_time=1.0),
            SessionMessage(session_id=1, content="{}", role="tool", response_time=1.5),
            SessionMessage(session_id=1, content="All pass.", role="assistant", response_time=2.0),
        ],
    )

    messages = build_messages(session, "and the lint?")

    assert messages == [
        {"role": "user", "content": "run the tests"},
        {"role": "assistant", "content": "All pass."},
        {"role": "system", "content": HISTORY_CONTEXT_NOTE},
        {"role": "user", "content": "and the lint?"},
    ]


def test_update_session_skips_the_history_it_sent_even_with_tool_messages_in_it(
    db: Database, profile_id: int
) -> None:
    session: Session | None = create_new_session(db, profile_id)
    assert session is not None
    first_turn = _make_response(
        messages=[
            Message(role="user", content="run the tests", response_time=1.0),
            Message(role="tool", content='{"tool": "bash"}', response_time=1.5),
            Message(role="assistant", content="All pass.", response_time=2.0),
        ]
    )
    session = update_session(db, session, first_turn)
    assert session is not None
    sent = build_messages(session, "and the lint?")
    second_turn = _make_response(
        messages=[
            *(Message(role=m["role"], content=m["content"], response_time=3.0) for m in sent),
            Message(role="assistant", content="Clean.", response_time=4.0),
        ]
    )

    result = update_session(db, session, second_turn, sent_prefix_length=len(sent) - 1)

    assert result is not None
    assert [m.content for m in result.messages] == [
        "run the tests",
        '{"tool": "bash"}',
        "All pass.",
        "and the lint?",
        "Clean.",
    ]


@pytest.mark.asyncio
async def test_compress_session_leaves_tool_messages_out_of_the_summary(
    db: Database, profile_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session: Session | None = create_new_session(db, profile_id)
    assert session is not None
    assert session.id is not None
    create_message(db, session.id, "run the tests", "user", 1.0)
    create_message(db, session.id, '{"tool": "bash", "observation": "raw output"}', "tool", 1.5)
    create_message(db, session.id, "All pass.", "assistant", 2.0)
    session = get_session(db, session.id)
    assert session is not None
    captured_prompts: list[str] = []

    async def fake_chat(
        _self: OllamaClient, messages: list[dict[str, str]], **_kwargs: object
    ) -> Response:
        captured_prompts.append(messages[0]["content"])
        return _make_response()

    monkeypatch.setattr(OllamaClient, "chat", fake_chat)
    client = OllamaClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)

    await compress_session(db, session, client)

    assert "raw output" not in captured_prompts[0]
    assert "assistant: All pass." in captured_prompts[0]


def test_new_session_is_untitled_and_unsaved(db: Database, profile_id: int) -> None:
    session = new_session(profile_id)

    assert session.id is None
    assert session.name is None
    assert session.profile_id == profile_id
    assert session.messages == []
    assert get_session(db, 1) is None


def test_ensure_persisted_saves_a_new_session_once(db: Database, profile_id: int) -> None:
    saved = ensure_persisted(db, new_session(profile_id))

    assert saved.id is not None
    assert get_session(db, saved.id) is not None
    assert ensure_persisted(db, saved) is saved


def _titled_session(db: Database, profile_id: int, *contents: tuple[str, str]) -> Session:
    session = create_session(db, profile_id)
    assert session.id is not None
    for role, content in contents:
        create_message(db, session.id, content, role, 1.0)
    reloaded = get_session(db, session.id)
    assert reloaded is not None
    return reloaded


def _title_client(monkeypatch: pytest.MonkeyPatch, title: str, prompts: list[str]) -> OllamaClient:
    async def fake_chat(
        _self: OllamaClient, messages: list[dict[str, str]], **kwargs: object
    ) -> Response:
        prompts.append(messages[0]["content"])
        assert kwargs["stream"] is False
        response = _make_response()
        response.response = title
        return response

    monkeypatch.setattr(OllamaClient, "chat", fake_chat)
    return OllamaClient(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)


@pytest.mark.asyncio
async def test_generate_session_title_names_the_session_from_its_first_exchange(
    db: Database, profile_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _titled_session(
        db,
        profile_id,
        ("user", "File: notes.md"),
        ("user", "How do I sort a dict?"),
        ("assistant", "Use sorted()."),
    )
    prompts: list[str] = []
    client = _title_client(monkeypatch, '"Sorting Python dicts."\nextra line', prompts)

    result = await generate_session_title(db, session, client)

    assert result.name == "Sorting Python dicts"
    assert "User: How do I sort a dict?" in prompts[0]
    assert "Assistant: Use sorted()." in prompts[0]


@pytest.mark.asyncio
async def test_generate_session_title_caps_the_length(
    db: Database, profile_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _titled_session(db, profile_id, ("user", "hi"), ("assistant", "hello"))
    client = _title_client(monkeypatch, "word " * 40, [])

    result = await generate_session_title(db, session, client)

    assert result.name is not None
    assert len(result.name) <= 60


@pytest.mark.asyncio
async def test_generate_session_title_keeps_no_name_on_an_empty_reply(
    db: Database, profile_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _titled_session(db, profile_id, ("user", "hi"), ("assistant", "hello"))
    client = _title_client(monkeypatch, "  \n ", [])

    result = await generate_session_title(db, session, client)

    assert result.name is None


@pytest.mark.asyncio
async def test_generate_session_title_skips_a_named_or_unanswered_session(
    db: Database, profile_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    unanswered = _titled_session(db, profile_id, ("user", "hi"))
    named = _titled_session(db, profile_id, ("user", "hi"), ("assistant", "hello"))
    assert named.id is not None
    rename_session(db, named.id, "Mine")
    named = get_session(db, named.id) or named
    prompts: list[str] = []
    client = _title_client(monkeypatch, "Generated", prompts)

    assert (await generate_session_title(db, unanswered, client)).name is None
    assert (await generate_session_title(db, named, client)).name == "Mine"
    assert (await generate_session_title(db, new_session(profile_id), client)).id is None
    assert prompts == []


@pytest.mark.asyncio
async def test_generate_session_title_keeps_a_name_given_meanwhile(
    db: Database, profile_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _titled_session(db, profile_id, ("user", "hi"), ("assistant", "hello"))
    assert session.id is not None
    rename_session(db, session.id, "Renamed by hand")
    client = _title_client(monkeypatch, "Generated", [])

    result = await generate_session_title(db, session, client)

    assert result.name == "Renamed by hand"
