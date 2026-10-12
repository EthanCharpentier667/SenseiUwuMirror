"""List the tools currently available to the agent."""

from rich.table import Table
from rich.text import Text

from sensai.ui.command import CommandContext


async def tool_execute(context: CommandContext, args: list[str]) -> None:
    """Display the current tool names and descriptions."""
    if args:
        await context.ui.on_system_message("Usage: /tool")
        return
    if not context.agent.tools:
        await context.ui.on_system_message("No tools available.")
        return

    table = Table(title="Available Tools", show_header=True, header_style="bold magenta")
    table.add_column("Tool", style="cyan")
    table.add_column("Description")
    for tool in context.agent.tools:
        table.add_row(Text(tool.name), Text(tool.description))

    await context.ui.on_system_message(table)
