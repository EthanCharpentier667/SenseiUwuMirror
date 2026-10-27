"""List the tools available to the agent, and enable or disable them one by one."""

import json

from rich.table import Table
from rich.text import Text

from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import update_profile_settings
from sensai.ui.command import CommandContext

USAGE = "Usage: /tools [enable|disable <name>]"


def _save_disabled_tools(context: CommandContext) -> None:
    """Keep the disabled tools in the active profile, for the next launches."""
    profile = ProfileManager.current_profile
    if not profile or not profile.id:
        return
    try:
        settings = json.loads(profile.settings) if profile.settings else {}
    except json.JSONDecodeError:
        settings = {}
    settings["disabled_tools"] = sorted(context.config.features.disabled_tools)
    settings_str = json.dumps(settings)
    update_profile_settings(context.database, profile.id, settings_str)
    profile.settings = settings_str


async def _list_tools(context: CommandContext) -> None:
    """Display every tool with its description and whether it is enabled."""
    if not context.agent.tools:
        await context.ui.on_system_message("No tools available.")
        return

    available = {tool.name for tool in context.agent.available_tools()}
    table = Table(title="Tools", show_header=True, header_style="bold magenta")
    table.add_column("Tool", style="cyan")
    table.add_column("Status")
    table.add_column("Description")
    for tool in context.agent.tools:
        status = "[green]on[/green]" if tool.name in available else "[red]off[/red]"
        table.add_row(Text(tool.name), status, Text(tool.description))

    await context.ui.on_system_message(table)


async def _set_tool(context: CommandContext, name: str, *, enabled: bool) -> None:
    """Enable or disable one tool by name, and save that choice."""
    if name not in {tool.name for tool in context.agent.tools}:
        await context.ui.on_system_message(f"[bold red]Unknown tool: {name}.[/bold red]")
        return
    context.config.features.set_tool(name, enabled=enabled)
    _save_disabled_tools(context)
    state = "enabled" if enabled else "disabled"
    await context.ui.on_system_message(f"[bold green]Tool {name} {state}.[/bold green]")


async def tool_execute(context: CommandContext, args: list[str]) -> None:
    """Execute the /tools command: list the tools, or enable or disable one."""
    if not args:
        await _list_tools(context)
    elif len(args) == 2 and args[0] in {"enable", "disable"}:  # noqa: PLR2004
        await _set_tool(context, args[1], enabled=args[0] == "enable")
    else:
        await context.ui.on_system_message(USAGE)
