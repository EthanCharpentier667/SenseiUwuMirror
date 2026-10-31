"""Async Interface for handling events emitted by the core AI logic."""

from typing import Any, Protocol


class AsyncUIHandler(Protocol):
    """Protocol defining the interface for the Event Manager."""

    async def on_stream_chunk(self, chunk: str) -> None:
        """Called when a new piece of text is streamed from the model."""
        ...  # pragma: no cover

    async def on_stream_end(self) -> None:
        """Called when a streaming response has finished."""
        ...  # pragma: no cover

    async def on_tool_call_request(self, name: str, arguments: dict[str, Any]) -> bool:
        """Called when a tool call requires user approval.

        Returns:
            True to approve the tool call, False to cancel.
        """
        ...  # pragma: no cover

    async def on_tool_call_result(
        self, name: str, result: Any, *, show_output: bool = False
    ) -> None:
        """Called when a tool has finished executing."""
        ...  # pragma: no cover

    async def render_output(self, content: Any, *, title: str = "Output") -> None:
        """Display content formatted in output mode (e.g. tool/sandbox output)."""
        ...  # pragma: no cover

    async def on_error(self, error: Exception | str, *, title: str = "Error") -> None:
        """Called when an error occurs in the pipeline or tool execution."""
        ...  # pragma: no cover

    async def on_thinking_chunk(self, chunk: str) -> None:
        """Called when a new piece of text is streamed from the model during the thinking phase."""
        ...  # pragma: no cover

    async def on_system_message(self, message: Any) -> None:
        """Called when the system needs to display a generic message to the user."""
        ...  # pragma: no cover

    async def on_prompt(self, payload: dict[str, Any]) -> None:
        """Called with a request to the model exactly as it is about to be sent."""
        ...  # pragma: no cover

    async def on_context_warning(self, used: int, limit: int) -> None:
        """Called when a prompt of ``used`` tokens nears the ``limit`` of the context window."""
        ...  # pragma: no cover

    async def start_spinner(self, message: str) -> None:
        """Start a loading spinner with a message."""
        ...  # pragma: no cover

    async def stop_spinner(self) -> None:
        """Stop the currently active loading spinner."""
        ...  # pragma: no cover

    async def prompt_choice(
        self, title: str, text: str, choices: list[tuple[str, str]]
    ) -> str | None:
        """Prompt the user to select an option from a list of choices."""
        ...  # pragma: no cover

    async def prompt_checklist(
        self,
        title: str,
        text: str,
        choices: list[tuple[str, str]],
        checked: list[str],
        *,
        extra: str | None = None,
    ) -> tuple[str, list[str]] | None:
        """Prompt the user to tick any number of choices.

        Returns which button confirmed the dialog ("ok", or "extra" for the optional
        ``extra`` button) with the ticked values, or None if the dialog was cancelled.
        """
        ...  # pragma: no cover

    async def prompt_input(self, title: str, text: str) -> str | None:
        """Prompt the user to input a free-form text string."""
        ...  # pragma: no cover
