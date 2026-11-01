"""Tests for the Question/Form system."""

from unittest.mock import AsyncMock, patch

import pytest

from sensai.ui.cli import CLIHandler
from sensai.ui.forms import Question, prompt_form


@pytest.mark.asyncio
async def test_prompt_form_collects_all_answers() -> None:
    questions = [
        Question(
            key="color",
            title="Color",
            text="Pick a color",
            choices=[("red", "Red"), ("blue", "Blue")],
        ),
        Question(key="size", title="Size", text="Enter size", choices=[("s", "Small")]),
    ]
    handler = AsyncMock()
    handler.prompt_question.side_effect = ["red", "s"]

    result = await prompt_form(handler, questions)

    assert result == {"color": "red", "size": "s"}
    assert handler.prompt_question.call_count == 2


@pytest.mark.asyncio
async def test_prompt_form_empty() -> None:
    handler = AsyncMock()
    result = await prompt_form(handler, [])
    assert result == {}


@pytest.mark.asyncio
async def test_prompt_form_preserves_none_answers() -> None:
    questions = [Question(key="q", title="T", text="T", choices=[("a", "A")])]
    handler = AsyncMock()
    handler.prompt_question.return_value = None

    result = await prompt_form(handler, questions)
    assert result == {"q": None}


@pytest.mark.asyncio
async def test_prompt_question_predefined_choice() -> None:
    handler = CLIHandler()
    question = Question(
        key="q",
        title="Title",
        text="Text",
        choices=[("a", "Option A"), ("b", "Option B")],
    )

    with patch("sensai.ui.cli.PromptSession") as mock_session_cls:
        mock_session_cls.return_value.prompt_async = AsyncMock(return_value="1")
        result = await handler.prompt_question(question)

    assert result == "a"


@pytest.mark.asyncio
async def test_prompt_question_second_choice() -> None:
    handler = CLIHandler()
    question = Question(
        key="q",
        title="Title",
        text="Text",
        choices=[("a", "Option A"), ("b", "Option B")],
    )

    with patch("sensai.ui.cli.PromptSession") as mock_session_cls:
        mock_session_cls.return_value.prompt_async = AsyncMock(return_value="2")
        result = await handler.prompt_question(question)

    assert result == "b"


@pytest.mark.asyncio
async def test_prompt_question_other_triggers_input() -> None:
    handler = CLIHandler()
    question = Question(
        key="q",
        title="Title",
        text="Text",
        choices=[("a", "Option A")],
        allow_other=True,
    )

    with patch("sensai.ui.cli.PromptSession") as mock_session_cls:
        mock_session_cls.return_value.prompt_async = AsyncMock(side_effect=["2", "custom answer"])
        result = await handler.prompt_question(question)

    assert result == "custom answer"


@pytest.mark.asyncio
async def test_prompt_question_other_cancelled_returns_none() -> None:
    handler = CLIHandler()
    question = Question(
        key="q",
        title="Title",
        text="Text",
        choices=[("a", "Option A")],
        allow_other=True,
    )

    with patch("sensai.ui.cli.PromptSession") as mock_session_cls:
        mock_session_cls.return_value.prompt_async = AsyncMock(side_effect=["2", ""])
        result = await handler.prompt_question(question)

    assert result is None


@pytest.mark.asyncio
async def test_prompt_question_allow_other_false() -> None:
    handler = CLIHandler()
    question = Question(
        key="q",
        title="Title",
        text="Text",
        choices=[("a", "Option A")],
        allow_other=False,
    )

    with patch("sensai.ui.cli.PromptSession") as mock_session_cls:
        mock_session_cls.return_value.prompt_async = AsyncMock(return_value="1")
        result = await handler.prompt_question(question)

    assert result == "a"


@pytest.mark.asyncio
async def test_prompt_question_cancelled_returns_none() -> None:
    handler = CLIHandler()
    question = Question(key="q", title="Title", text="Text", choices=[("a", "Option A")])

    with patch("sensai.ui.cli.PromptSession") as mock_session_cls:
        mock_session_cls.return_value.prompt_async = AsyncMock(side_effect=KeyboardInterrupt)
        result = await handler.prompt_question(question)

    assert result is None


@pytest.mark.asyncio
async def test_prompt_question_no_choices_free_text() -> None:
    handler = CLIHandler()
    question = Question(key="q", title="Title", text="Text", allow_other=True)

    with patch("sensai.ui.cli.PromptSession") as mock_session_cls:
        mock_session_cls.return_value.prompt_async = AsyncMock(return_value="free text answer")
        result = await handler.prompt_question(question)

    assert result == "free text answer"
