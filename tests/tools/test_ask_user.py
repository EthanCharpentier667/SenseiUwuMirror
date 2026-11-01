"""Tests for AskUserTool."""

from unittest.mock import AsyncMock

import pytest

from sensai.features.tools.ask_user import AskUserTool


@pytest.mark.asyncio
async def test_ask_user_returns_selected_choice() -> None:
    handler = AsyncMock()
    handler.prompt_question.return_value = "Python"
    tool = AskUserTool(handler)

    result = await tool.execute(question="Preferred language?", choices=["Python", "Rust"])

    assert result == "Python"
    question = handler.prompt_question.call_args[0][0]
    assert question.text == "Preferred language?"
    assert ("Python", "Python") in question.choices
    assert ("Rust", "Rust") in question.choices


@pytest.mark.asyncio
async def test_ask_user_no_choices_uses_free_text() -> None:
    handler = AsyncMock()
    handler.prompt_question.return_value = "some free answer"
    tool = AskUserTool(handler)

    result = await tool.execute(question="Tell me something")

    assert result == "some free answer"
    question = handler.prompt_question.call_args[0][0]
    assert question.choices == []
    assert question.allow_other is True


@pytest.mark.asyncio
async def test_ask_user_cancelled_returns_none() -> None:
    handler = AsyncMock()
    handler.prompt_question.return_value = None
    tool = AskUserTool(handler)

    result = await tool.execute(question="Proceed?", choices=["Yes", "No"])

    assert result is None


@pytest.mark.asyncio
async def test_ask_user_allow_other_false() -> None:
    handler = AsyncMock()
    handler.prompt_question.return_value = "Yes"
    tool = AskUserTool(handler)

    await tool.execute(question="Proceed?", choices=["Yes", "No"], allow_other=False)

    question = handler.prompt_question.call_args[0][0]
    assert question.allow_other is False


def test_ask_user_tool_name() -> None:
    handler = AsyncMock()
    tool = AskUserTool(handler)
    assert tool.name == "ask_user"
