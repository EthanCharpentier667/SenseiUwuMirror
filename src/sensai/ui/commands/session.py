"""List, switch, create, rename and delete the profile's chat sessions."""

import shlex
from collections.abc import Iterable
from datetime import UTC, datetime

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document
from rich.console import Group
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from sensai.data.database.database import Database
from sensai.data.profile.manager import get_current_profile
from sensai.data.session.manager import ensure_persisted, new_session
from sensai.data.session.session import (
    Session,
    delete_session,
    find_sessions_by_name,
    get_session,
    list_sessions,
    rename_session,
)
from sensai.ui.command import CommandContext

USAGE = "Usage: /session [list | new | switch <name or id> | rename [name] | delete [name or id]]"
RECAP_EXCHANGES = 3
_MINUTE = 60
_HOUR = 60 * _MINUTE
_DAY = 24 * _HOUR


_AGES = ((_MINUTE, None, "just now"), (_HOUR, _MINUTE, "min ago"), (_DAY, _HOUR, "h ago"))


def _ago(value: datetime | str | None) -> str:
    """How long ago a naive UTC timestamp was, roughly."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return "unknown"
    if value is None:
        return "never"
    seconds = (datetime.now(UTC).replace(tzinfo=None) - value).total_seconds()
    for limit, unit, suffix in _AGES:
        if seconds < limit:
            return suffix if unit is None else f"{int(seconds // unit)} {suffix}"
    return "yesterday" if seconds < 2 * _DAY else f"{int(seconds // _DAY)} days ago"


def _label(session: Session) -> str:
    return session.name or "untitled"


def _summary_line(session: Session) -> str:
    """A session's name, size and age, as the picker and the completer show it."""
    return f"{_label(session)} · {session.message_count} msgs · {_ago(session.last_updated)}"


def _quote(name: str) -> str:
    """``name`` as a single command-line argument, quoted only when it has to be."""
    try:
        if shlex.split(name) == [name]:
            return name
    except ValueError:
        pass
    return shlex.quote(name)


def _switch(context: CommandContext, session: Session) -> None:
    """Make ``session`` the current one, in the app and in this command's context."""
    context.session = session
    if context.switch_session is not None:
        context.switch_session(session)


def _recap(session: Session) -> Group:
    """A header for the session, then its last exchanges, as they appeared in the chat."""
    shown = [m for m in session.messages if m.role in {"user", "assistant"} and m.content]
    users = [i for i, m in enumerate(shown) if m.role == "user"]
    start = users[-RECAP_EXCHANGES] if len(users) >= RECAP_EXCHANGES else 0
    parts: list[Text | Markdown] = [
        Text.from_markup(
            f"[bold cyan]Switched to “{_label(session)}”[/bold cyan] "
            f"[dim]— {len(session.messages)} messages, last used "
            f"{_ago(session.last_updated)}[/dim]"
        )
    ]
    if start > 0:
        hidden = "earlier messages summarized" if session.summary else f"{start} earlier messages"
        parts.append(Text(f"({hidden})", style="dim"))
    for message in shown[start:]:
        if message.role == "user":
            parts.append(Text(f"\nVous > {message.content}", style="bold"))
        else:
            parts.append(Markdown(message.content))
    return Group(*parts)


async def _open(context: CommandContext, session_id: int) -> None:
    """Switch to a saved session by ID, showing its last exchanges."""
    if session_id == context.session.id:
        await context.ui.on_system_message("Already in this session.")
        return
    session = get_session(context.database, session_id)
    if session is None or session.profile_id != context.session.profile_id:
        await context.ui.on_system_message(f"[bold red]No session #{session_id}.[/bold red]")
        return
    _switch(context, session)
    await context.ui.on_system_message(_recap(session))


async def _pick(context: CommandContext, sessions: list[Session], *, new: bool) -> int | None:
    """Let the user pick one of ``sessions``; ``0`` stands for a new session."""
    choices = [("0", "+ New session")] if new else []
    for session in sessions:
        current = " (current)" if session.id == context.session.id else ""
        choices.append((str(session.id), f"{_summary_line(session)}{current}"))
    choice = await context.ui.prompt_choice(
        title="Sessions", text="Select a session:", choices=choices
    )
    return int(choice) if choice is not None else None


async def _start_new(context: CommandContext) -> None:
    _switch(context, new_session(context.session.profile_id))
    await context.ui.on_system_message("[bold green]Started a new session.[/bold green]")


async def _picker(context: CommandContext) -> None:
    sessions = list_sessions(context.database, context.session.profile_id)
    session_id = await _pick(context, sessions, new=True)
    if session_id == 0:
        await _start_new(context)
    elif session_id is not None:
        await _open(context, session_id)


async def _list(context: CommandContext) -> None:
    sessions = list_sessions(context.database, context.session.profile_id)
    if not sessions:
        await context.ui.on_system_message("No saved sessions yet.")
        return
    table = Table(title="Sessions", show_header=True, header_style="bold magenta")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Name")
    table.add_column("Messages", justify="right")
    table.add_column("Last used")
    for session in sessions:
        name = Text(_label(session))
        if session.id == context.session.id:
            name.append(" (current)", style="bold green")
        table.add_row(str(session.id), name, str(session.message_count), _ago(session.last_updated))
    await context.ui.on_system_message(table)


async def _resolve(context: CommandContext, query: str, *, verb: str) -> int | None:
    """The ID of the session a name or ID designates, asking when several match."""
    if query.isdigit():
        return int(query)
    matches = find_sessions_by_name(context.database, context.session.profile_id, query)
    if not matches:
        await context.ui.on_system_message(f"[bold red]No session named “{query}”.[/bold red]")
        return None
    if len(matches) == 1:
        return matches[0].id
    await context.ui.on_system_message(f"Several sessions match “{query}”: pick one to {verb}.")
    return await _pick(context, matches, new=False)


async def _rename(context: CommandContext, args: list[str]) -> None:
    name = " ".join(args).strip()
    if not name:
        name = (
            await context.ui.prompt_input(
                title="Rename session", text=f"New name for “{_label(context.session)}”:"
            )
            or ""
        ).strip()
    if not name:
        return
    session = ensure_persisted(context.database, context.session)
    if session.id is None:
        return
    rename_session(context.database, session.id, name)
    _switch(context, get_session(context.database, session.id) or session)
    await context.ui.on_system_message(f"[bold green]Session renamed to “{name}”.[/bold green]")


async def _delete(context: CommandContext, args: list[str]) -> None:
    if args:
        session_id = await _resolve(context, " ".join(args), verb="delete")
    else:
        session_id = context.session.id
        if session_id is None:
            await context.ui.on_system_message("This session isn't saved yet: nothing to delete.")
            return
    if session_id is None:
        return
    session = get_session(context.database, session_id)
    if session is None or session.profile_id != context.session.profile_id:
        await context.ui.on_system_message(f"[bold red]No session #{session_id}.[/bold red]")
        return
    confirm = await context.ui.prompt_choice(
        title="Delete session",
        text=f"Delete “{_label(session)}” and its {len(session.messages)} messages for good?",
        choices=[("no", "No, keep it"), ("yes", "Yes, delete it")],
    )
    if confirm != "yes":
        return
    delete_session(context.database, session_id)
    await context.ui.on_system_message(f"[bold green]Deleted “{_label(session)}”.[/bold green]")
    if session_id == context.session.id:
        await _start_new(context)


class SessionNameCompleter(Completer):  # type: ignore[misc,unused-ignore]
    """Suggest the profile's session names after /session switch|delete."""

    def __init__(self, database: Database) -> None:
        """Complete against the sessions saved in this database, as they are when completing."""
        self.database = database

    def get_completions(
        self, document: Document, _complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Complete the name being typed, quoting it when the shell split would break it."""
        parts = document.text_before_cursor.split(" ", 2)
        profile = get_current_profile()
        if len(parts) < 3 or parts[1] not in {"switch", "delete"} or profile is None:  # noqa: PLR2004
            return
        if profile.id is None:
            return
        typed = parts[2]
        partial = typed.lstrip("\"'").lower()
        for session in list_sessions(self.database, profile.id):
            meta = f"#{session.id} · {session.message_count} msgs · {_ago(session.last_updated)}"
            if session.name and session.name.lower().startswith(partial):
                yield Completion(
                    _quote(session.name),
                    start_position=-len(typed),
                    display=session.name,
                    display_meta=meta,
                )
            elif not session.name and str(session.id).startswith(partial):
                yield Completion(
                    str(session.id), start_position=-len(typed), display_meta="untitled · " + meta
                )


async def session_execute(context: CommandContext, args: list[str]) -> None:
    """Execute the /session command: pick, list, start, switch, rename or delete sessions."""
    if not args:
        await _picker(context)
    elif args == ["list"]:
        await _list(context)
    elif args == ["new"]:
        await _start_new(context)
    elif args[0] == "switch" and len(args) >= 2:  # noqa: PLR2004
        session_id = await _resolve(context, " ".join(args[1:]), verb="open")
        if session_id is not None:
            await _open(context, session_id)
    elif args[0] == "rename":
        await _rename(context, args[1:])
    elif args[0] == "delete":
        await _delete(context, args[1:])
    else:
        await context.ui.on_system_message(USAGE)
