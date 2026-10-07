"""Help command."""

from rich.table import Table

from sensai.ui.command import CommandContext


async def help_execute(context: CommandContext, _args: list[str]) -> None:
    """Execute the /help command."""
    table = Table(title="Available Commands", show_header=True, header_style="bold magenta")
    table.add_column("Command", style="cyan")
    table.add_column("Description")

    table.add_row("/help", "List all available commands.")
    table.add_row("/logout", "Log out and clear saved credentials.")
    table.add_row("/prefs", "Manage preferences (list, add, remove, edit).")
    table.add_row("/inst", "Manage system instructions (list, add, remove, edit).")
    table.add_row("/settings", "Open interactive settings menu.")
    table.add_row("/model", "Change the AI model used in the current session.")
    table.add_row("/exit or /quit", "Exit the application.")

    await context.ui.on_system_message(table)
