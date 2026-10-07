"""CLI implementation of the AsyncUIHandler protocol."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from prompt_toolkit import PromptSession
from prompt_toolkit.shortcuts import input_dialog, radiolist_dialog
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from .protocol import AsyncUIHandler

if TYPE_CHECKING:
    from rich.status import Status


class CLIHandler(AsyncUIHandler):
    """CLI implementation of the Event Manager."""

    def __init__(self) -> None:
        """Initialize the CLI Handler with a rich console."""
        self.console = Console()
        self._spinner_status: Status | None = None

    async def start_spinner(self, message: str) -> None:
        """Start a loading spinner with a message."""
        if self._spinner_status is not None:
            self._spinner_status.stop()
        self._spinner_status = self.console.status(f"[cyan]{message}[/cyan]")
        self._spinner_status.start()

    async def stop_spinner(self) -> None:
        """Stop the currently active loading spinner."""
        if self._spinner_status is not None:
            self._spinner_status.stop()
            self._spinner_status = None

    async def on_stream_chunk(self, chunk: str) -> None:
        """Called when a new piece of text is streamed from the model."""
        await self.stop_spinner()
        self.console.out(chunk, end="")

    async def on_tool_call_request(self, name: str, arguments: dict[str, Any]) -> bool:
        """Ask the user to approve a tool call via the terminal."""
        json_str = json.dumps(arguments, indent=2, ensure_ascii=False)
        syntax = Syntax(json_str, "json", theme="monokai", word_wrap=True)
        panel = Panel(
            syntax, title=f"[bold blue]Tool Call Request: {name}[/bold blue]", border_style="blue"
        )
        self.console.print("\n")
        self.console.print(panel)

        session = PromptSession[str]()
        choice = await session.prompt_async("Approve this action? [Y/n]: ")
        return choice.strip().lower() in {"y", "yes", "o", "oui", ""}

    async def on_tool_call_result(self, name: str, result: Any) -> None:  # noqa: ARG002
        """Called when a tool has finished executing."""
        self.console.print(f"[bold green]✓ Tool '{name}' executed successfully.[/bold green]\n")

    async def on_error(self, error: Exception) -> None:
        """Called when an error occurs in the pipeline."""
        self.console.print(f"\n[bold red][Error]: {error}[/bold red]")

    async def on_system_message(self, message: Any) -> None:
        """Display a system message (like a command output)."""
        self.console.print(message)

    async def prompt_choice(
        self, title: str, text: str, choices: list[tuple[str, str]]
    ) -> str | None:
        """Prompt the user to select an option from a list of choices."""
        choice = await radiolist_dialog(
            title=title,
            text=text,
            values=choices,
        ).run_async()
        return str(choice) if choice is not None else None

    async def prompt_input(self, title: str, text: str) -> str | None:
        """Prompt the user to input a free-form text string."""
        choice = await input_dialog(title=title, text=text).run_async()
        return str(choice) if choice is not None else None
