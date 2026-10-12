"""Persona command for switching and listing agent personas."""

from sensai.persona.manager import get_persona, list_personas, load_personas
from sensai.ui.command import CommandContext


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
                await context.ui.on_system_message(
                    f"[bold green]Persona switched to '{key}': {persona.name}[/bold green]"
                )
            else:
                await context.ui.on_system_message(f"[red]Warning: persona '{key}' not found.[/red]")
        except (FileNotFoundError, ValueError) as exc:
            await context.ui.on_system_message(f"[red]Could not switch persona: {exc}[/red]")

    else:
        await context.ui.on_system_message(
            f"[red]Unknown subcommand: {subcmd}. Use list or switch.[/red]"
        )
