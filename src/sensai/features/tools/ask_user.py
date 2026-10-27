"""Tool that lets the model ask the user a structured question."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sensai.ui.forms import Question

from .tool import Tool

if TYPE_CHECKING:
    from sensai.ui.protocol import AsyncUIHandler


class AskUserTool(Tool):
    """Ask the user a question with optional predefined choices."""

    def __init__(self, ui_handler: AsyncUIHandler) -> None:
        """Initialize the AskUser tool with the active UI handler."""
        self._ui_handler = ui_handler
        super().__init__(
            name="ask_user",
            description=(
                "Ask the user a question. Use this when you need clarification or a choice "
                "from the user. Provide choices to present a selection list; omit them for "
                "a free-text answer."
            ),
            tool_type="function",
            parameters={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask the user.",
                    },
                    "choices": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of predefined choices to present.",
                    },
                    "allow_other": {
                        "type": "boolean",
                        "description": (
                            "Whether to show a free-text 'Other' option alongside choices."
                            " Defaults to true."
                        ),
                    },
                },
                "required": ["question"],
            },
            safe=True,
        )

    async def execute(self, *_args: Any, **kwargs: Any) -> str | None:
        """Present the question to the user and return their answer."""
        question_text: str = kwargs["question"]
        raw_choices: list[str] = kwargs.get("choices") or []
        allow_other: bool = kwargs.get("allow_other", True)

        question = Question(
            key="answer",
            title=question_text[:60],
            text=question_text,
            choices=[(c, c) for c in raw_choices],
            allow_other=allow_other if raw_choices else True,
        )
        return await self._ui_handler.prompt_question(question)
