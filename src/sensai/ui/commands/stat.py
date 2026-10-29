"""Stat command."""

from collections import Counter
from datetime import datetime

from rich.table import Table

from sensai.features.features import COMPRESSION
from sensai.ui.command import CommandContext

_NOT_AVAILABLE = "n/a"


def _fmt_int(value: int | None) -> str:
    return f"{value:,}" if value is not None else _NOT_AVAILABLE


def _fmt_date(value: datetime | str | None) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value) if value else _NOT_AVAILABLE


def _ratio(part: int | None, whole: int | None) -> str:
    if part is None or not whole:
        return _NOT_AVAILABLE
    return f"{part:,} / {whole:,} ({part / whole:.0%})"


def _default(value: object) -> str:
    return "default" if value is None else str(value)


def _add_session_rows(table: Table, context: CommandContext) -> None:
    session = context.session
    table.add_row("Session", f"{session.name or 'untitled'} (#{session.id})")
    table.add_row("Created", _fmt_date(session.created_at))
    table.add_row("Last activity", _fmt_date(session.last_updated))


def _add_token_rows(table: Table, context: CommandContext) -> None:
    session = context.session
    table.add_row("Prompt tokens", _fmt_int(session.prompt_eval_count))
    table.add_row("Generated tokens", _fmt_int(session.eval_count))
    table.add_row("Total tokens", _fmt_int(session.token_used))


def _add_message_rows(table: Table, context: CommandContext) -> None:
    messages = context.session.messages
    roles = Counter(message.role for message in messages)
    for role in ("user", "assistant", "tool"):
        table.add_row(f"{role.capitalize()} messages", _fmt_int(roles[role]))
    table.add_row("Total messages", _fmt_int(len(messages)))


def _add_context_rows(table: Table, context: CommandContext) -> None:
    session = context.session
    last_prompt = context.agent.last_prompt_tokens
    table.add_row("Last prompt", _fmt_int(last_prompt))
    table.add_row("Context window", _ratio(last_prompt, context.agent.num_ctx))

    compression = _ratio(last_prompt, context.config.compression_threshold)
    if not context.config.features.is_enabled(COMPRESSION):
        compression += " [dim](disabled)[/dim]"
    table.add_row("Compression threshold", compression)

    if session.summary and session.summarized_message_id is not None:
        folded = sum(
            1
            for message in session.messages
            if message.id is not None and message.id <= session.summarized_message_id
        )
        table.add_row("Summary", f"yes ({folded} messages folded)")
    else:
        table.add_row("Summary", "no")


def _add_config_rows(table: Table, context: CommandContext) -> None:
    agent = context.agent
    table.add_row("Model", agent.model)
    table.add_row("Persona", agent.persona_key or "default")
    table.add_row("Temperature", _default(agent.temperature))
    table.add_row("Top p", _default(agent.top_p))
    table.add_row("Context size (num_ctx)", _default(agent.num_ctx))
    table.add_row("Tools enabled", f"{len(agent.available_tools())} / {len(agent.tools)}")


async def stat_execute(context: CommandContext, _args: list[str]) -> None:
    """Execute the /stat command."""
    table = Table(title="Session Stats", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value")

    sections = (
        _add_session_rows,
        _add_token_rows,
        _add_message_rows,
        _add_context_rows,
        _add_config_rows,
    )
    for index, add_rows in enumerate(sections):
        if index:
            table.add_section()
        add_rows(table, context)

    await context.ui.on_system_message(table)
