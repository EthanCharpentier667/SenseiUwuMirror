"""Command registry and management for the CLI."""

import shlex
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

from sensai.data.database.database import Database
from sensai.ui.protocol import AsyncUIHandler


@dataclass
class CommandContext:
    """Context passed to commands when they are executed."""

    database: Database
    ui: AsyncUIHandler


@dataclass
class Command:
    """A slash command that can be executed in the CLI."""

    name: str
    description: str
    execute: Callable[[CommandContext, list[str]], Awaitable[None]]
    subcommands: list[str] = field(default_factory=list)


class SlashCommandCompleter(Completer):  # type: ignore[misc,unused-ignore]
    """Completer for slash commands."""

    def __init__(self, commands: dict[str, Command]) -> None:
        """Initialize the completer with available commands."""
        self.commands = commands

    def get_completions(self, document: Document, _complete_event: CompleteEvent) -> Any:
        """Yield completions if the text starts with a slash."""
        text = document.text_before_cursor
        if not text.startswith("/"):
            return

        words = text.split(" ")

        if len(words) == 1:
            word = words[0]
            for cmd_name, cmd in self.commands.items():
                if cmd_name.startswith(word):
                    yield Completion(
                        cmd_name,
                        start_position=-len(word),
                        display=cmd_name,
                        display_meta=cmd.description,
                    )

        elif len(words) == 2:  # noqa: PLR2004
            cmd_name = words[0]
            if cmd_name in self.commands:
                cmd = self.commands[cmd_name]
                sub_word = words[1]
                for subcmd in cmd.subcommands:
                    if subcmd.startswith(sub_word):
                        yield Completion(
                            subcmd,
                            start_position=-len(sub_word),
                            display=subcmd,
                        )


class CommandRegistry:
    """Registry for CLI slash commands."""

    def __init__(self) -> None:
        """Initialize the registry."""
        self._commands: dict[str, Command] = {}

    def register(self, command: Command) -> None:
        """Register a new command.

        Args:
            command (Command): The command to register.
        """
        self._commands[command.name] = command

    def get_completer(self) -> SlashCommandCompleter:
        """Get a prompt_toolkit completer for all registered commands."""
        return SlashCommandCompleter(self._commands)

    async def execute(self, user_input: str, context: CommandContext) -> None:
        """Execute a slash command.

        Args:
            user_input (str): The raw input starting with a slash.
            context (CommandContext): The application context for the command.
        """
        parts = user_input.strip().split()
        if not parts:
            return

        command_name = parts[0]
        args = parts[1:]

        if command_name not in self._commands:
            await context.ui.on_system_message(
                f"[bold red]Unknown command:[/bold red] {command_name}. "
                "Type /help to see available commands."
            )
            return

        command = self._commands[command_name]
        try:
            if command_name == "/mcp":  # Only split the arguments for /mcp
                args = shlex.split(user_input)[1:]  # to handle quoted JSON correctly
            await command.execute(context, args)
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001
            await context.ui.on_error(e)

    def get_all_commands(self) -> list[Command]:
        """Get a list of all registered commands."""
        return list(self._commands.values())
