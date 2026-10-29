"""Persona command for switching and listing agent personas."""

from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import load_profile_settings, save_profile_settings
from sensai.features.persona.manager import get_persona, list_personas, load_personas
from sensai.ui.command import CommandContext


def _save_persona_to_profile(context: CommandContext, key: str) -> None:
    """Keep the persona in the active profile, so the next launches start with it."""
    profile = ProfileManager.current_profile
    if profile and profile.id:
        settings = load_profile_settings(profile)
        settings["persona"] = key
        save_profile_settings(context.database, profile, settings)


async def persona_execute(context: CommandContext, args: list[str]) -> None:
    """Execute the /persona command."""
    personas_file = context.config.personas_file
    subcmd = args[0] if args else "list"

    if subcmd == "list":
        try:
            personas = load_personas(personas_file)
            keys = list_personas(personas)
            if keys:
                for key in keys:
                    p = personas[key]
                    await context.ui.on_system_message(
                        f"  [cyan]{key}[/cyan]: {p.name} — {p.description}"
                    )
            else:
                await context.ui.on_system_message("[dim]No personas found.[/dim]")
        except (FileNotFoundError, ValueError) as exc:
            await context.ui.on_system_message(f"[red]Could not load personas: {exc}[/red]")

    elif subcmd == "switch":
        if len(args) < 2:  # noqa: PLR2004
            await context.ui.on_system_message("[red]Usage: /persona switch <key>[/red]")
            return
        key = args[1]
        try:
            personas = load_personas(personas_file)
            persona = get_persona(personas, key)
            if persona is not None:
                context.agent.system_prompt = persona.system_prompt
                context.agent.persona_key = key
                _save_persona_to_profile(context, key)
                await context.ui.on_system_message(
                    f"[bold green]Persona switched to '{key}': {persona.name}[/bold green]"
                )
            else:
                msg = f"[red]Warning: persona '{key}' not found.[/red]"
                await context.ui.on_system_message(msg)
        except (FileNotFoundError, ValueError) as exc:
            await context.ui.on_system_message(f"[red]Could not switch persona: {exc}[/red]")

    else:
        await context.ui.on_system_message(
            f"[red]Unknown subcommand: {subcmd}. Use list or switch.[/red]"
        )
