"""Tests for the /session command."""

from typing import Any

import pytest
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from rich.console import Console, Group
from rich.table import Table

from sensai.data.database.database import Database
from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import create_profile, get_profile
from sensai.data.session.manager import new_session
from sensai.data.session.message import create_message
from sensai.data.session.session import Session, create_session, get_session
from sensai.ui.command import CommandContext
from sensai.ui.commands.session import USAGE, SessionNameCompleter, session_execute


class ScriptedUI:
    """Records what is shown and answers the dialogs from a script."""

    def __init__(self, choices: list[str | None] | None = None, text: str | None = None) -> None:
        """Answer each prompt_choice with the next scripted choice, prompt_input with ``text``."""
        self.messages: list[Any] = []
        self.choices = list(choices or [])
        self.offered: list[list[tuple[str, str]]] = []
        self.text = text

    async def on_system_message(self, message: Any) -> None:
        self.messages.append(message)

    async def prompt_choice(self, title: str, text: str, choices: list[tuple[str, str]]) -> Any:
        del title, text
        self.offered.append(choices)
        return self.choices.pop(0)

    async def prompt_input(self, title: str, text: str) -> str | None:
        del title, text
        return self.text


def _context(db: Database, session: Session, ui: ScriptedUI) -> tuple[CommandContext, list[Any]]:
    switched: list[Session] = []
    context = CommandContext(
        database=db,
        ui=ui,  # type: ignore[arg-type]
        agent=None,  # type: ignore[arg-type]
        config=None,  # type: ignore[arg-type]
        session=session,
        switch_session=switched.append,
    )
    return context, switched


def _saved(db: Database, profile_id: int, name: str | None, *exchanges: str) -> Session:
    session = create_session(db, profile_id, name)
    assert session.id is not None
    for index, content in enumerate(exchanges):
        create_message(db, session.id, content, "user" if index % 2 == 0 else "assistant", 1.0)
    return get_session(db, session.id) or session


def _text(message: Any) -> str:
    console = Console(record=True, width=200)
    console.print(message)
    return console.export_text()


@pytest.mark.asyncio
async def test_session_new_switches_to_an_unsaved_session(db: Database, profile_id: int) -> None:
    current = _saved(db, profile_id, "Old")
    context, switched = _context(db, current, ScriptedUI())

    await session_execute(context, ["new"])

    assert len(switched) == 1
    assert switched[0].id is None
    assert switched[0].profile_id == profile_id
    assert context.session is switched[0]


@pytest.mark.asyncio
async def test_session_list_shows_the_profiles_sessions(db: Database, profile_id: int) -> None:
    current = _saved(db, profile_id, "Current", "hi", "hello")
    _saved(db, profile_id, None)
    ui = ScriptedUI()
    context, _ = _context(db, current, ui)

    await session_execute(context, ["list"])

    assert isinstance(ui.messages[0], Table)
    text = _text(ui.messages[0])
    assert "Current (current)" in text
    assert "untitled" in text


@pytest.mark.asyncio
async def test_session_list_without_sessions(db: Database, profile_id: int) -> None:
    ui = ScriptedUI()
    context, _ = _context(db, new_session(profile_id), ui)

    await session_execute(context, ["list"])

    assert ui.messages == ["No saved sessions yet."]


@pytest.mark.asyncio
async def test_session_switch_by_name_shows_the_last_exchanges(
    db: Database, profile_id: int
) -> None:
    turns = [f"question {n}" if n % 2 == 0 else f"answer {n}" for n in range(10)]
    target = _saved(db, profile_id, "Python help", *turns)
    ui = ScriptedUI()
    context, switched = _context(db, new_session(profile_id), ui)

    await session_execute(context, ["switch", "Python", "help"])

    assert [session.id for session in switched] == [target.id]
    assert isinstance(ui.messages[0], Group)
    text = _text(ui.messages[0])
    assert "Switched to “Python help”" in text
    assert "(4 earlier messages)" in text
    assert "question 4" in text
    assert "answer 9" in text
    assert "question 2" not in text


@pytest.mark.asyncio
async def test_session_switch_by_id(db: Database, profile_id: int) -> None:
    target = _saved(db, profile_id, None, "hi", "hello")
    context, switched = _context(db, new_session(profile_id), ScriptedUI())

    await session_execute(context, ["switch", str(target.id)])

    assert [session.id for session in switched] == [target.id]


@pytest.mark.asyncio
async def test_session_switch_to_another_profiles_session_is_refused(
    db: Database, profile_id: int
) -> None:
    other = create_profile(db, "Other", "secret").id
    assert other is not None
    theirs = _saved(db, other, "Secret")
    ui = ScriptedUI()
    context, switched = _context(db, new_session(profile_id), ui)

    await session_execute(context, ["switch", str(theirs.id)])

    assert switched == []
    assert f"No session #{theirs.id}" in ui.messages[0]


@pytest.mark.asyncio
async def test_session_switch_to_the_current_session_does_nothing(
    db: Database, profile_id: int
) -> None:
    current = _saved(db, profile_id, "Here")
    ui = ScriptedUI()
    context, switched = _context(db, current, ui)

    await session_execute(context, ["switch", "Here"])

    assert switched == []
    assert ui.messages == ["Already in this session."]


@pytest.mark.asyncio
async def test_session_switch_with_an_unknown_name(db: Database, profile_id: int) -> None:
    ui = ScriptedUI()
    context, switched = _context(db, new_session(profile_id), ui)

    await session_execute(context, ["switch", "nothing"])

    assert switched == []
    assert "No session named “nothing”" in ui.messages[0]


@pytest.mark.asyncio
async def test_session_switch_with_an_ambiguous_name_asks_which(
    db: Database, profile_id: int
) -> None:
    first = _saved(db, profile_id, "Python help")
    second = _saved(db, profile_id, "Python tests")
    _saved(db, profile_id, "Rust")
    ui = ScriptedUI(choices=[str(first.id)])
    context, switched = _context(db, new_session(profile_id), ui)

    await session_execute(context, ["switch", "py"])

    assert {value for value, _ in ui.offered[0]} == {str(first.id), str(second.id)}
    assert [session.id for session in switched] == [first.id]


@pytest.mark.asyncio
async def test_session_picker_switches_or_starts_a_new_session(
    db: Database, profile_id: int
) -> None:
    target = _saved(db, profile_id, "Target", "hi", "hello")
    ui = ScriptedUI(choices=[str(target.id), "0", None])
    context, switched = _context(db, new_session(profile_id), ui)

    await session_execute(context, [])
    await session_execute(context, [])
    await session_execute(context, [])

    assert ui.offered[0][0] == ("0", "+ New session")
    assert "Target · 2 msgs" in ui.offered[0][1][1]
    assert "(current)" in ui.offered[1][1][1]
    assert switched[0].id == target.id
    assert switched[1].id is None
    assert len(switched) == 2


@pytest.mark.asyncio
async def test_session_rename_saves_an_unsaved_session(db: Database, profile_id: int) -> None:
    context, switched = _context(db, new_session(profile_id), ScriptedUI())

    await session_execute(context, ["rename", "My", "chat"])

    assert switched[0].id is not None
    assert switched[0].name == "My chat"
    assert (get_session(db, switched[0].id) or switched[0]).name == "My chat"


@pytest.mark.asyncio
async def test_session_rename_asks_for_the_name(db: Database, profile_id: int) -> None:
    current = _saved(db, profile_id, "Old")
    context, switched = _context(db, current, ScriptedUI(text="  New  "))

    await session_execute(context, ["rename"])

    assert switched[0].name == "New"


@pytest.mark.asyncio
async def test_session_rename_cancelled(db: Database, profile_id: int) -> None:
    current = _saved(db, profile_id, "Old")
    context, switched = _context(db, current, ScriptedUI(text=None))

    await session_execute(context, ["rename"])

    assert switched == []
    assert (get_session(db, current.id or 0) or current).name == "Old"


@pytest.mark.asyncio
async def test_session_delete_the_current_one_starts_a_new_session(
    db: Database, profile_id: int
) -> None:
    current = _saved(db, profile_id, "Doomed", "hi")
    assert current.id is not None
    ui = ScriptedUI(choices=["yes"])
    context, switched = _context(db, current, ui)

    await session_execute(context, ["delete"])

    assert get_session(db, current.id) is None
    assert [session.id for session in switched] == [None]


@pytest.mark.asyncio
async def test_session_delete_another_one_by_name(db: Database, profile_id: int) -> None:
    current = _saved(db, profile_id, "Current")
    doomed = _saved(db, profile_id, "Doomed")
    assert doomed.id is not None
    context, switched = _context(db, current, ScriptedUI(choices=["yes"]))

    await session_execute(context, ["delete", "Doomed"])

    assert get_session(db, doomed.id) is None
    assert switched == []


@pytest.mark.asyncio
async def test_session_delete_needs_confirmation(db: Database, profile_id: int) -> None:
    current = _saved(db, profile_id, "Kept")
    assert current.id is not None
    context, switched = _context(db, current, ScriptedUI(choices=["no"]))

    await session_execute(context, ["delete"])

    assert get_session(db, current.id) is not None
    assert switched == []


@pytest.mark.asyncio
async def test_session_delete_an_unsaved_session(db: Database, profile_id: int) -> None:
    ui = ScriptedUI()
    context, _ = _context(db, new_session(profile_id), ui)

    await session_execute(context, ["delete"])

    assert "nothing to delete" in ui.messages[0]


@pytest.mark.asyncio
async def test_session_usage(db: Database, profile_id: int) -> None:
    ui = ScriptedUI()
    context, _ = _context(db, new_session(profile_id), ui)

    await session_execute(context, ["frobnicate"])
    await session_execute(context, ["switch"])

    assert ui.messages == [USAGE, USAGE]


def _completions(db: Database, text: str) -> list[tuple[str, str]]:
    completer = SessionNameCompleter(db)
    return [
        (completion.text, completion.display_meta_text)
        for completion in completer.get_completions(Document(text), CompleteEvent())
    ]


def test_completer_suggests_names_and_quotes_them(db: Database, profile_id: int) -> None:
    ProfileManager.current_profile = get_profile(db, profile_id)
    _saved(db, profile_id, "Python help", "hi")
    _saved(db, profile_id, "Pandas")
    _saved(db, profile_id, "Rust")

    found = dict(_completions(db, "/session switch p"))

    assert set(found) == {"'Python help'", "Pandas"}
    assert "1 msgs" in found["'Python help'"]


def test_completer_suggests_ids_of_untitled_sessions(db: Database, profile_id: int) -> None:
    ProfileManager.current_profile = get_profile(db, profile_id)
    untitled = _saved(db, profile_id, None)

    assert [text for text, _ in _completions(db, "/session delete ")] == [str(untitled.id)]


def test_completer_only_completes_switch_and_delete(db: Database, profile_id: int) -> None:
    ProfileManager.current_profile = get_profile(db, profile_id)
    _saved(db, profile_id, "Python")

    assert _completions(db, "/session rename P") == []
    assert _completions(db, "/session switch") == []
