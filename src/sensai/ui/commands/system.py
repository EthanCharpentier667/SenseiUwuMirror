"""System commands."""

import sys

from sensai.ui.command import CommandContext


async def exit_execute(context: CommandContext, _args: list[str]) -> None:
    """Execute the /exit or /quit command."""
    await context.ui.on_system_message("[dim]Exiting application...[/dim]")
    sys.exit(0)
