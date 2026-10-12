"""Authentication commands."""

import sys

from sensai.core.state import clear_credentials
from sensai.ui.command import CommandContext


async def logout_execute(context: CommandContext, _args: list[str]) -> None:
    """Execute the /logout command."""
    clear_credentials()
    await context.ui.on_system_message(
        "[bold green]Successfully logged out. Credentials cleared from local state.[/bold green]"
    )
    await context.ui.on_system_message(
        "[dim]Exiting application... Please restart to log in again.[/dim]"
    )
    sys.exit(0)
