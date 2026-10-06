"""Preferences and instructions commands."""

from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import (
    update_profile_instructions,
    update_profile_preferences,
)
from sensai.ui.command import CommandContext


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


async def prefs_execute(context: CommandContext, args: list[str]) -> None:
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


async def inst_execute(context: CommandContext, args: list[str]) -> None:
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
