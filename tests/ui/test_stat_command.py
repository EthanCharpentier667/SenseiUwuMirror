"""Tests for the /stat command."""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from rich.console import Console
from rich.table import Table

from sensai.data.session.message import Message
from sensai.data.session.session import Session
from sensai.features.features import COMPRESSION, Features
from sensai.ui.command import CommandContext
from sensai.ui.commands.persona import persona_execute
from sensai.ui.commands.stat import stat_execute


class CapturingUI:
    def __init__(self) -> None:
        """Start with no captured messages."""
        self.messages: list[Any] = []

    async def on_system_message(self, message: Any) -> None:
        self.messages.append(message)


def _session(**overrides: Any) -> Session:
    messages = [
        Message(id=1, role="user", content="hi", response_time=0.0),
        Message(id=2, role="assistant", content="hello", response_time=0.0),
        Message(id=3, role="tool", content="42", response_time=0.0),
        Message(id=4, role="user", content="thanks", response_time=0.0),
    ]
    fields: dict[str, Any] = {
        "id": 7,
        "name": "cart review",
        "prompt_eval_count": 1200,
        "eval_count": 300,
        "token_used": 1500,
        "created_at": datetime(2026, 10, 29, 9, 30, tzinfo=UTC),
        "last_updated": datetime(2026, 10, 29, 10, 0, tzinfo=UTC),
        "messages": messages,
    }
    fields.update(overrides)
    return Session(**fields)


def _agent(**overrides: Any) -> SimpleNamespace:
    tools = [SimpleNamespace(name="bash"), SimpleNamespace(name="web_search")]
    fields: dict[str, Any] = {
        "model": "qwen3",
        "persona_key": None,
        "temperature": 0.2,
        "top_p": None,
        "num_ctx": 8000,
        "last_prompt_tokens": None,
        "tools": tools,
        "available_tools": lambda: tools[:1],
        "system_prompt": None,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _context(
    ui: CapturingUI,
    *,
    session: Session | None = None,
    agent: Any = None,
    features: Any = None,
    personas_file: str = "",
) -> CommandContext:
    config = SimpleNamespace(
        compression_threshold=4000, features=features or Features(), personas_file=personas_file
    )
    return CommandContext(
        database=None,  # type: ignore[arg-type]
        ui=ui,  # type: ignore[arg-type]
        agent=agent or _agent(),  # type: ignore[arg-type]
        config=config,  # type: ignore[arg-type]
        session=session or _session(),
    )


async def _render(ctx: CommandContext) -> str:
    await stat_execute(ctx, [])
    ui: CapturingUI = ctx.ui  # type: ignore[assignment]
    assert len(ui.messages) == 1
    table = ui.messages[0]
    assert isinstance(table, Table)
    console = Console(record=True, width=120)
    console.print(table)
    return console.export_text()


def _row(text: str, metric: str) -> str:
    return next(line for line in text.splitlines() if metric in line)


@pytest.mark.asyncio
async def test_stat_shows_tokens_and_message_counts() -> None:
    text = await _render(_context(CapturingUI()))

    assert "cart review (#7)" in text
    assert "2026-10-29 09:30" in _row(text, "Created")
    assert "1,200" in _row(text, "Prompt tokens")
    assert "300" in _row(text, "Generated tokens")
    assert "1,500" in _row(text, "Total tokens")
    assert "2" in _row(text, "User messages")
    assert "1" in _row(text, "Assistant messages")
    assert "1" in _row(text, "Tool messages")
    assert "4" in _row(text, "Total messages")


@pytest.mark.asyncio
async def test_stat_context_is_not_available_before_first_turn() -> None:
    text = await _render(_context(CapturingUI()))

    assert "n/a" in _row(text, "Last prompt")
    assert "n/a" in _row(text, "Context window")
    assert "n/a" in _row(text, "Compression threshold")
    assert "no" in _row(text, "Summary")


@pytest.mark.asyncio
async def test_stat_context_fill_percentages() -> None:
    ctx = _context(CapturingUI(), agent=_agent(last_prompt_tokens=2000))
    text = await _render(ctx)

    assert "2,000 / 8,000 (25%)" in _row(text, "Context window")
    assert "2,000 / 4,000 (50%)" in _row(text, "Compression threshold")
    assert "disabled" not in _row(text, "Compression threshold")


@pytest.mark.asyncio
async def test_stat_without_num_ctx_shows_not_available() -> None:
    ctx = _context(CapturingUI(), agent=_agent(last_prompt_tokens=2000, num_ctx=None))
    text = await _render(ctx)

    assert "n/a" in _row(text, "Context window")
    assert "default" in _row(text, "num_ctx")


@pytest.mark.asyncio
async def test_stat_marks_disabled_compression() -> None:
    features = Features.from_disabled([COMPRESSION])
    text = await _render(_context(CapturingUI(), features=features))

    assert "disabled" in _row(text, "Compression threshold")


@pytest.mark.asyncio
async def test_stat_counts_messages_folded_into_summary() -> None:
    session = _session(summary="Camille checks the cart.", summarized_message=2)
    text = await _render(_context(CapturingUI(), session=session))

    assert "yes (2 messages folded)" in _row(text, "Summary")


@pytest.mark.asyncio
async def test_stat_shows_runtime_config() -> None:
    text = await _render(_context(CapturingUI(), agent=_agent(persona_key="sensei_wu")))

    assert "qwen3" in _row(text, "Model")
    assert "sensei_wu" in _row(text, "Persona")
    assert "0.2" in _row(text, "Temperature")
    assert "default" in _row(text, "Top p")
    assert "1 / 2" in _row(text, "Tools enabled")


@pytest.mark.asyncio
async def test_persona_switch_tracks_active_key(tmp_path: Path) -> None:
    personas_file = tmp_path / "personas.json"
    personas_file.write_text(
        json.dumps({"wu": {"name": "Wu", "description": "d", "system_prompt": "Be wise."}})
    )
    agent = _agent()
    ctx = _context(CapturingUI(), agent=agent, personas_file=str(personas_file))

    await persona_execute(ctx, ["switch", "wu"])

    assert agent.persona_key == "wu"
    assert agent.system_prompt == "Be wise."
