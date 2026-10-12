"""CLI implementation of the AsyncUIHandler protocol."""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING, Any

from prompt_toolkit import PromptSession
from prompt_toolkit.shortcuts import input_dialog, radiolist_dialog
from rich.console import Console, RenderableType
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from .protocol import AsyncUIHandler

if TYPE_CHECKING:
    from rich.status import Status


class CLIHandler(AsyncUIHandler):
    """CLI implementation of the Event Manager."""

    def __init__(self) -> None:
        """Initialize the CLI Handler with a rich console."""
        self.console = Console()
        self._spinner_status: Status | None = None
        self._live: Live | None = None
        self._stream_buffer: str = ""

    @property
    def is_spinner_active(self) -> bool:
        """Return whether a loading spinner is currently active."""
        return self._spinner_status is not None

    async def start_spinner(self, message: str) -> None:
        """Start a loading spinner with a message."""
        if self._spinner_status is not None:
            self._spinner_status.update(f"[cyan]{message}[/cyan]")
            return
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
        self._stream_buffer += chunk
        if self._live is None:
            self._live = Live(
                Markdown(self._stream_buffer),
                console=self.console,
                refresh_per_second=12,
                vertical_overflow="visible",
            )
            self._live.start()
        else:
            self._live.update(Markdown(self._stream_buffer))

    async def on_stream_end(self) -> None:
        """Called when text streaming has finished."""
        if self._live is not None:
            self._live.stop()
            self._live = None
            self._stream_buffer = ""

    async def on_tool_call_request(self, name: str, arguments: dict[str, Any]) -> bool:
        """Ask the user to approve a tool call via the terminal."""
        await self.stop_spinner()
        await self.on_stream_end()
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

    def _format_output_content(self, result: Any) -> RenderableType:
        """Format arbitrary tool output content for display."""
        if isinstance(result, (dict, list)):
            return Syntax(
                json.dumps(result, indent=2, ensure_ascii=False),
                "json",
                theme="monokai",
                word_wrap=True,
            )
        if isinstance(result, str):
            trimmed = result.strip()
            if (trimmed.startswith("{") and trimmed.endswith("}")) or (
                trimmed.startswith("[") and trimmed.endswith("]")
            ):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    parsed = json.loads(trimmed)
                    return Syntax(
                        json.dumps(parsed, indent=2, ensure_ascii=False),
                        "json",
                        theme="monokai",
                        word_wrap=True,
                    )
            if "```" in result or trimmed.startswith("#"):
                return Markdown(result)
            return Text.from_ansi(result)
        return Text.from_ansi(str(result))

    def format_output(self, content: Any, *, title: str = "Output") -> Panel:
        """Create a formatted output Panel for arbitrary content."""
        rendered = self._format_output_content(content)
        return Panel(
            rendered,
            title=f"[bold cyan]{title}[/bold cyan]",
            border_style="cyan",
        )

    async def render_output(self, content: Any, *, title: str = "Output") -> None:
        """Display content formatted in output mode (e.g. tool or sandbox output)."""
        await self.stop_spinner()
        await self.on_stream_end()
        panel = self.format_output(content, title=title)
        self.console.print(panel)
        self.console.print("")

    async def on_tool_call_result(self, name: str, result: Any) -> None:
        """Called when a tool has finished executing."""
        await self.stop_spinner()
        await self.on_stream_end()

        if isinstance(result, dict) and (
            "error" in result or ("exit_code" in result and result.get("exit_code") != 0)
        ):
            err_msg = str(result.get("error") or result.get("stderr") or result)
            await self.on_error(err_msg, title=f"Tool Error: {name}")
            return

        if result in (None, "", {}):
            self.console.print(f"[bold green]✓ Tool '{name}' executed successfully.[/bold green]\n")
            return

        self.console.print(f"[bold green]✓ Tool '{name}' executed successfully:[/bold green]")
        await self.render_output(result, title=f"Tool Output: {name}")

    async def on_error(self, error: Exception | str, *, title: str = "Error") -> None:
        """Called when an error occurs in the pipeline or during tool execution."""
        await self.stop_spinner()
        await self.on_stream_end()
        msg = str(error)
        panel = Panel(
            Text(msg, style="bold red"),
            title=f"[bold red]{title}[/bold red]",
            border_style="red",
        )
        self.console.print("\n")
        self.console.print(panel)

    async def on_thinking_chunk(self, chunk: str) -> None:
        """Called when a new piece of text is streamed from the model during the thinking phase."""
        await self.stop_spinner()
        self.console.print(chunk, style="dim", end="", markup=False, highlight=False)

    async def on_system_message(self, message: Any) -> None:
        """Display a system message (like a command output)."""
        await self.stop_spinner()
        await self.on_stream_end()
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
