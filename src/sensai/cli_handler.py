"""CLI implementation of the AsyncUIHandler protocol."""

import asyncio
import json
from typing import Any

from .events import AsyncUIHandler


class CLIHandler(AsyncUIHandler):
    """CLI implementation of the Event Manager."""

    async def on_stream_chunk(self, chunk: str) -> None:
        """Called when a new piece of text is streamed from the model."""
        print(chunk, end="", flush=True)  # noqa: T201

    async def on_tool_call_request(self, name: str, arguments: dict[str, Any]) -> bool:
        """Ask the user to approve a tool call via the terminal."""
        print(f"\n\nThe AI wants to call '{name}' with the following arguments:")  # noqa: T201
        print(json.dumps(arguments, indent=2, ensure_ascii=False))  # noqa: T201
        choice = await asyncio.to_thread(input, "Approve? [y/n] : ")
        return choice.strip().lower() in {"y", "yes", "o", "oui", ""}

    async def on_tool_call_result(self, name: str, result: Any) -> None:
        """Called when a tool has finished executing."""

    async def on_error(self, error: Exception) -> None:
        """Called when an error occurs in the pipeline."""
        print(f"\n[Error]: {error}")  # noqa: T201
