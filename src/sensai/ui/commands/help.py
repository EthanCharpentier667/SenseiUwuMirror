"""Help command."""

from collections.abc import Awaitable, Callable

from rich.table import Table
from rich.text import Text

from sensai.ui.command import CommandContext, CommandRegistry


def make_help_execute(
    registry: CommandRegistry,
) -> Callable[[CommandContext, list[str]], Awaitable[None]]:
    """Build the /help command, listing whatever the registry holds when it runs.

    Args:
        registry (CommandRegistry): The registry whose commands /help lists.
    """

    async def help_execute(context: CommandContext, _args: list[str]) -> None:
        """Execute the /help command."""
        table = Table(title="Available Commands", show_header=True, header_style="bold magenta")
        table.add_column("Command", style="cyan")
        table.add_column("Description")
        for command in sorted(registry.get_all_commands(), key=lambda command: command.name):
            name = command.name
            if command.subcommands:
                name += f" [{' | '.join(command.subcommands)}]"
            table.add_row(Text(name), Text(command.description))

        await context.ui.on_system_message(table)

    return help_execute
