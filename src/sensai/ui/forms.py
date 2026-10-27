"""Question and Form primitives for interactive CLI prompts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .protocol import AsyncUIHandler


@dataclass
class Question:
    """A single question with optional predefined choices and a free-text fallback."""

    key: str
    title: str
    text: str
    choices: list[tuple[str, str]] = field(default_factory=list)
    allow_other: bool = True


async def prompt_form(
    handler: AsyncUIHandler, questions: list[Question]
) -> dict[str, str | None]:
    """Run a sequence of questions and return answers keyed by question.key."""
    return {q.key: await handler.prompt_question(q) for q in questions}
