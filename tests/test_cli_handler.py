"""Tests for the ``sensai.cli_handler`` module."""

from typing import Any

import pytest
from rich.console import Console

from sensai.ui import CLIHandler


@pytest.mark.asyncio
async def test_on_stream_chunk(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    await handler.on_stream_chunk("Hello")
    await handler.on_stream_chunk(" World")

    captured = capsys.readouterr()
    assert captured.out == "Hello World"


@pytest.mark.asyncio
async def test_on_tool_call_request_approved(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def mock_prompt_async(*args: Any, **kwargs: Any) -> str:
        return "y"

    monkeypatch.setattr("sensai.ui.cli.PromptSession.prompt_async", mock_prompt_async)

    handler = CLIHandler()
    result = await handler.on_tool_call_request("my_tool", {"arg": "value"})

    assert result is True
    captured = capsys.readouterr()
    assert "Tool Call Request: my_tool" in captured.out
    assert '"arg": "value"' in captured.out


@pytest.mark.asyncio
async def test_on_tool_call_request_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_prompt_async(*args: Any, **kwargs: Any) -> str:
        return "n"

    monkeypatch.setattr("sensai.ui.cli.PromptSession.prompt_async", mock_prompt_async)

    handler = CLIHandler()
    result = await handler.on_tool_call_request("my_tool", {})
    assert result is False


@pytest.mark.asyncio
async def test_on_tool_call_result() -> None:
    handler = CLIHandler()
    await handler.on_tool_call_result("my_tool", "result")


@pytest.mark.asyncio
async def test_on_error(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    await handler.on_error(ValueError("Oups"))

    captured = capsys.readouterr()
    assert "[Error]: Oups" in captured.out


@pytest.mark.asyncio
async def test_on_thinking_chunk_is_dimmed(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    handler.console = Console(force_terminal=True, color_system="standard")
    await handler.on_thinking_chunk("Hmm")
    captured = capsys.readouterr()
    assert captured.out == "\033[2mHmm\033[0m"


@pytest.mark.asyncio
async def test_on_thinking_chunk_prints_brackets_literally(
    capsys: pytest.CaptureFixture[str],
) -> None:
    handler = CLIHandler()
    await handler.on_thinking_chunk("[bold]not markup[/bold] [/dim]")
    captured = capsys.readouterr()
    assert captured.out == "[bold]not markup[/bold] [/dim]"
