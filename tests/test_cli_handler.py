"""Tests for the ``sensai.cli_handler`` module."""

import asyncio
from typing import Any

import pytest

from sensai.cli_handler import CLIHandler


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
    async def mock_to_thread(func: Any, prompt: str) -> str:
        return "y"

    monkeypatch.setattr(asyncio, "to_thread", mock_to_thread)

    handler = CLIHandler()
    result = await handler.on_tool_call_request("my_tool", {"arg": "value"})

    assert result is True
    captured = capsys.readouterr()
    assert "The AI wants to call 'my_tool'" in captured.out
    assert '"arg": "value"' in captured.out


@pytest.mark.asyncio
async def test_on_tool_call_request_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mock_to_thread(func: Any, prompt: str) -> str:
        return "n"

    monkeypatch.setattr(asyncio, "to_thread", mock_to_thread)

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
