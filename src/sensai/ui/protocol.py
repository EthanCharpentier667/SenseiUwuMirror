"""Async Interface for handling events emitted by the core AI logic."""

from typing import Any, Protocol


class AsyncUIHandler(Protocol):
    """Protocol defining the interface for the Event Manager."""

    async def on_stream_chunk(self, chunk: str) -> None:
        """Called when a new piece of text is streamed from the model."""
        ...  # pragma: no cover

    async def on_tool_call_request(self, name: str, arguments: dict[str, Any]) -> bool:
        """Called when a tool call requires user approval.

        Returns:
            True to approve the tool call, False to cancel.
        """
        ...  # pragma: no cover

    async def on_tool_call_result(self, name: str, result: Any) -> None:
        """Called when a tool has finished executing."""
        ...  # pragma: no cover

    async def on_error(self, error: Exception) -> None:
        """Called when an error occurs in the pipeline."""
        ...  # pragma: no cover
