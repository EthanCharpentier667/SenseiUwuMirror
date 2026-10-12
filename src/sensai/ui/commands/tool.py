"""List the tools currently available to the agent."""

from rich.table import Table
from rich.text import Text

from sensai.ui.command import CommandContext


async def tool_execute(context: CommandContext, args: list[str]) -> None:
    """Display the current tool names and descriptions."""
    if args:
        await context.ui.on_system_message("Usage: /tool or /tools")
        return
    if not context.agent.tools:
        await context.ui.on_system_message("No tools available.")
        return

    table = Table(
        title="Available Tools",
        caption=f"{len(context.agent.tools)} tool(s) available",
        header_style="bold magenta",
        show_lines=True,
        expand=True,
    )
    table.add_column("Tool", style="bold cyan", no_wrap=True)
    table.add_column("Description", ratio=1)
    for tool in sorted(context.agent.tools, key=lambda tool: tool.name):
        table.add_row(Text(tool.name), Text(tool.description))

    await context.ui.on_system_message(table)
