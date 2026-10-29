"""Tests for the ``sensai.ui.app`` module."""

import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.console import Console

from sensai.client import Response
from sensai.data.database.database import Database
from sensai.data.session.document import get_documents_by_message
from sensai.data.session.manager import get_current_session, new_session
from sensai.data.session.message import Message, create_message
from sensai.data.session.session import Session, create_session
from sensai.features.features import COMPRESSION, RAG, TITLE, Features
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


class _TitleClient:
    """Stands in for OllamaClient, answering title prompts with ``title``."""

    def __init__(self, title: str | Exception) -> None:
        """Answer each chat with ``title``, or raise it when it is an exception."""
        self.title = title
        self.calls = 0

    async def chat(self, **_kwargs: object) -> Response:
        self.calls += 1
        if isinstance(self.title, Exception):
            raise self.title
        return _response([], self.title)


def _response(messages: list[Message], text: str) -> Response:
    return Response(
        response=text,
        respond_time=1.0,
        request_time=0.0,
        total_duration=0,
        model="qwen3",
        tools=[],
        messages=messages,
        prompt_eval_count=10,
        eval_count=5,
        token_used=15,
        status_code=200,
        tool_calls=[],
        stop_reason="stop",
    )


def _chat_app(
    db: Database, session: Session, title: str | Exception = "Greetings", *disabled: str
) -> tuple[CLIApp, _TitleClient]:
    """A CLIApp whose agent answers every prompt with "hello"."""

    async def run(messages: list[dict[str, str]]) -> Response:
        sent = [Message(role=m["role"], content=m["content"], response_time=0.0) for m in messages]
        reply = Message(role="assistant", content="hello", response_time=1.0)
        return _response([*sent, reply], "hello")

    client = _TitleClient(title)
    app = CLIApp.__new__(CLIApp)
    app.database = db
    app.session = session
    app.client = client  # type: ignore[assignment]
    app.console = Console(file=io.StringIO())
    app.config = SimpleNamespace(  # type: ignore[assignment]
        features=Features.from_disabled([RAG, COMPRESSION, *disabled]), verbose=True
    )
    app.agent = SimpleNamespace(  # type: ignore[assignment]
        run=run, ui_handler=None, last_prompt_tokens=None, model="qwen3", read_documents=[]
    )
    return app, client


@pytest.mark.asyncio
async def test_first_turn_saves_the_session_and_names_it(db: Database, profile_id: int) -> None:
    app, client = _chat_app(db, new_session(profile_id))

    await app._handle_chat("hi")  # noqa: SLF001
    await app._handle_chat("again")  # noqa: SLF001

    assert app.session.id is not None
    assert app.session.name == "Greetings"
    assert [m.content for m in app.session.messages] == ["hi", "hello", "again", "hello"]
    assert client.calls == 1
    assert get_current_session() is app.session


@pytest.mark.asyncio
async def test_title_is_skipped_when_the_feature_is_off(db: Database, profile_id: int) -> None:
    app, client = _chat_app(db, new_session(profile_id), "Greetings", TITLE)

    await app._handle_chat("hi")  # noqa: SLF001

    assert app.session.name is None
    assert client.calls == 0


@pytest.mark.asyncio
async def test_title_is_skipped_for_a_named_session(db: Database, profile_id: int) -> None:
    app, client = _chat_app(db, create_session(db, profile_id, "Mine"))

    await app._handle_chat("hi")  # noqa: SLF001

    assert app.session.name == "Mine"
    assert client.calls == 0


@pytest.mark.asyncio
async def test_a_failed_title_does_not_fail_the_turn(db: Database, profile_id: int) -> None:
    app, _ = _chat_app(db, new_session(profile_id), RuntimeError("model down"))

    await app._handle_chat("hi")  # noqa: SLF001

    assert app.session.name is None
    assert [m.content for m in app.session.messages] == ["hi", "hello"]
    assert "model down" in app.console.file.getvalue()  # type: ignore[attr-defined]


def test_switch_session_updates_the_current_session(db: Database, profile_id: int) -> None:
    app, _ = _chat_app(db, new_session(profile_id))
    app.agent.last_prompt_tokens = 1234
    other = create_session(db, profile_id, "Other")

    app.switch_session(other)

    assert app.session is other
    assert get_current_session() is other
    assert app.agent.last_prompt_tokens == 0
