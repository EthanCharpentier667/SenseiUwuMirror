"""Built-in slash commands for the CLI."""

import sys

from rich.table import Table

from sensai.core.state import clear_credentials
from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import update_profile_instructions, update_profile_preferences
from sensai.ui.command import Command, CommandContext, CommandRegistry


async def _help_execute(context: CommandContext, _args: list[str]) -> None:
    """Execute the /help command."""
    table = Table(title="Available Commands", show_header=True, header_style="bold magenta")
    table.add_column("Command", style="cyan")
    table.add_column("Description")

    table.add_row("/help", "List all available commands.")
    table.add_row("/logout", "Log out and clear saved credentials.")
    table.add_row("/prefs", "Manage preferences (list, add, remove, edit).")
    table.add_row("/inst", "Manage system instructions (list, add, remove, edit).")

    await context.ui.on_system_message(table)


async def _logout_execute(context: CommandContext, _args: list[str]) -> None:
    """Execute the /logout command."""
    clear_credentials()
    await context.ui.on_system_message(
        "[bold green]Successfully logged out. Credentials cleared from local state.[/bold green]"
    )
    await context.ui.on_system_message(
        "[dim]Exiting application... Please restart to log in again.[/dim]"
    )
    sys.exit(0)


async def _handle_list(context: CommandContext, lines: list[str], name: str) -> None:
    if not lines:
        await context.ui.on_system_message(f"[dim]No {name} set.[/dim]")
        return
    for i, line in enumerate(lines):
        await context.ui.on_system_message(f"  [cyan]{i}[/cyan]: {line}")


async def _handle_add(
    context: CommandContext, args: list[str], lines: list[str], name: str
) -> bool:
    text = " ".join(args[1:])
    if not text:
        await context.ui.on_system_message(f"[red]Usage: /{name[:5]} add <text>[/red]")
        return False
    lines.append(text)
    return True


async def _handle_remove(
    context: CommandContext, args: list[str], lines: list[str], name: str
) -> bool:
    if len(args) < 2 or not args[1].isdigit():  # noqa: PLR2004
        await context.ui.on_system_message(f"[red]Usage: /{name[:5]} remove <index>[/red]")
        return False
    idx = int(args[1])
    if idx < 0 or idx >= len(lines):
        await context.ui.on_system_message(f"[red]Invalid index {idx}.[/red]")
        return False
    removed = lines.pop(idx)
    await context.ui.on_system_message(f"[dim]Removed: {removed}[/dim]")
    return True


async def _handle_edit(
    context: CommandContext, args: list[str], lines: list[str], name: str
) -> bool:
    if len(args) < 3 or not args[1].isdigit():  # noqa: PLR2004
        await context.ui.on_system_message(f"[red]Usage: /{name[:5]} edit <index> <new text>[/red]")
        return False
    idx = int(args[1])
    if idx < 0 or idx >= len(lines):
        await context.ui.on_system_message(f"[red]Invalid index {idx}.[/red]")
        return False
    text = " ".join(args[2:])
    lines[idx] = text
    await context.ui.on_system_message(f"[dim]Updated {name[:-1]} {idx}.[/dim]")
    return True


async def _manage_list_command(
    context: CommandContext, args: list[str], lines: list[str], name: str
) -> list[str] | None:
    """Helper to manage list, add, remove, edit for preferences and instructions."""
    if not args or args[0] == "list":
        await _handle_list(context, lines, name)
        return None

    subcmd = args[0]
    changed = False

    if subcmd == "add":
        changed = await _handle_add(context, args, lines, name)
    elif subcmd == "remove":
        changed = await _handle_remove(context, args, lines, name)
    elif subcmd == "edit":
        changed = await _handle_edit(context, args, lines, name)
    else:
        await context.ui.on_system_message(
            f"[red]Unknown subcommand: {subcmd}. Use list, add, remove, or edit.[/red]"
        )
        return None

    return lines if changed else None


async def _prefs_execute(context: CommandContext, args: list[str]) -> None:
    """Execute the /prefs command."""
    profile = ProfileManager.current_profile
    if not profile or not profile.id:
        await context.ui.on_system_message("[red]No active profile found.[/red]")
        return

    current_prefs = profile.preferences or ""
    pref_lines = current_prefs.split("\n") if current_prefs else []

    new_lines = await _manage_list_command(context, args, pref_lines, "preferences")
    if new_lines is not None:
        new_prefs = "\n".join(new_lines)
        update_profile_preferences(context.database, profile.id, new_prefs)
        profile.preferences = new_prefs
        await context.ui.on_system_message(
            "[bold green]Preferences updated successfully.[/bold green]"
        )


async def _inst_execute(context: CommandContext, args: list[str]) -> None:
    """Execute the /inst command."""
    profile = ProfileManager.current_profile
    if not profile or not profile.id:
        await context.ui.on_system_message("[red]No active profile found.[/red]")
        return

    current_inst = profile.instructions or ""
    inst_lines = current_inst.split("\n") if current_inst else []

    new_lines = await _manage_list_command(context, args, inst_lines, "instructions")
    if new_lines is not None:
        new_inst = "\n".join(new_lines)
        update_profile_instructions(context.database, profile.id, new_inst)
        profile.instructions = new_inst
        await context.ui.on_system_message(
            "[bold green]Instructions updated successfully.[/bold green]"
        )


async def _exit_execute(context: CommandContext, _args: list[str]) -> None:
    """Execute the /exit or /quit command."""
    await context.ui.on_system_message("[dim]Exiting application...[/dim]")
    sys.exit(0)


def setup_builtin_commands(registry: CommandRegistry) -> None:
    """Register all built-in commands."""
    registry.register(Command("/help", "List all available commands.", _help_execute))
    registry.register(Command("/logout", "Log out and clear saved credentials.", _logout_execute))
    registry.register(Command("/exit", "Exit the application.", _exit_execute))
    registry.register(Command("/quit", "Exit the application.", _exit_execute))
    registry.register(
        Command(
            "/prefs",
            "Manage preferences.",
            _prefs_execute,
            subcommands=["list", "add", "remove", "edit"],
        )
    )
    registry.register(
        Command(
            "/inst",
            "Manage system instructions.",
            _inst_execute,
            subcommands=["list", "add", "remove", "edit"],
        )
    )
