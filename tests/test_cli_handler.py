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
    await handler.on_stream_end()

    captured = capsys.readouterr()
    assert "Hello World" in captured.out


@pytest.mark.asyncio
async def test_on_stream_chunk_markdown_code(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    await handler.on_stream_chunk("Here is code:\n\n```python\n")
    await handler.on_stream_chunk("def foo():\n    return 42\n```\n")
    await handler.on_stream_end()

    captured = capsys.readouterr()
    assert "Here is code:" in captured.out
    assert "def foo():" in captured.out
    assert "return 42" in captured.out


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
async def test_on_tool_call_result_empty(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    await handler.on_tool_call_result("my_tool", None)
    captured = capsys.readouterr()
    assert "Tool 'my_tool' executed successfully." in captured.out


@pytest.mark.asyncio
async def test_on_tool_call_result_output_text(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    await handler.on_tool_call_result("sandbox", "stdout:\nHello sandbox!\nexit code: 0")
    captured = capsys.readouterr()
    assert "Tool 'sandbox' executed successfully:" in captured.out
    assert "Tool Output: sandbox" in captured.out
    assert "Hello sandbox!" in captured.out


@pytest.mark.asyncio
async def test_on_tool_call_result_output_dict(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    await handler.on_tool_call_result("fetch", {"status": "ok", "count": 5})
    captured = capsys.readouterr()
    assert "Tool Output: fetch" in captured.out
    assert '"status": "ok"' in captured.out


@pytest.mark.asyncio
async def test_on_tool_call_result_output_json_string(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    await handler.on_tool_call_result("search", '{"items": [1, 2]}')
    captured = capsys.readouterr()
    assert "Tool Output: search" in captured.out
    assert '"items"' in captured.out


@pytest.mark.asyncio
async def test_on_tool_call_result_output_markdown(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    await handler.on_tool_call_result("generator", "```python\nprint('gen')\n```")
    captured = capsys.readouterr()
    assert "Tool Output: generator" in captured.out
    assert "print('gen')" in captured.out


@pytest.mark.asyncio
async def test_on_tool_call_result_error_dict(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    await handler.on_tool_call_result(
        "failing_tool", {"error": "command not found", "exit_code": 127}
    )
    captured = capsys.readouterr()
    assert "Tool Error: failing_tool" in captured.out
    assert "command not found" in captured.out


@pytest.mark.asyncio
async def test_on_error(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    await handler.on_error(ValueError("Oups"))

    captured = capsys.readouterr()
    assert "Error" in captured.out
    assert "Oups" in captured.out


@pytest.mark.asyncio
async def test_on_error_custom_title(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    await handler.on_error("Something went wrong", title="Tool Error: execute_code")

    captured = capsys.readouterr()
    assert "Tool Error: execute_code" in captured.out
    assert "Something went wrong" in captured.out


@pytest.mark.asyncio
async def test_spinner_lifecycle() -> None:
    handler = CLIHandler()
    await handler.start_spinner("Thinking...")
    assert handler.is_spinner_active is True

    # Smooth update
    await handler.start_spinner("Compressing...")
    assert handler.is_spinner_active is True

    await handler.stop_spinner()
    assert handler.is_spinner_active is False


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


@pytest.mark.asyncio
async def test_on_system_message_markup(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    await handler.on_system_message("[dim]Exiting application...[/dim]")
    captured = capsys.readouterr()
    assert "Exiting application..." in captured.out
    assert "[dim]" not in captured.out


@pytest.mark.asyncio
async def test_on_system_message_non_string(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    await handler.on_system_message(42)
    captured = capsys.readouterr()
    assert "42" in captured.out


@pytest.mark.asyncio
async def test_render_output_direct(capsys: pytest.CaptureFixture[str]) -> None:
    handler = CLIHandler()
    await handler.render_output("custom command output", title="My Sandbox")
    captured = capsys.readouterr()
    assert "My Sandbox" in captured.out
    assert "custom command output" in captured.out
