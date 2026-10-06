"""Settings command."""

import json

from prompt_toolkit.shortcuts import input_dialog, radiolist_dialog

from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import update_profile_settings
from sensai.ui.command import CommandContext


async def settings_execute(context: CommandContext, _args: list[str]) -> None:
    """Execute the /settings command."""
    profile = ProfileManager.current_profile
    if not profile or not profile.id:
        await context.ui.on_system_message("[red]No active profile found.[/red]")
        return

    settings = json.loads(profile.settings) if profile.settings else {}

    while True:
        trust = settings.get("trust_level", context.agent.trust_level)
        comp = settings.get("compression_threshold", context.config.compression_threshold)
        url = settings.get("url", context.config.url)

        choice = await radiolist_dialog(
            title="Settings Menu",
            text="Choose a setting to modify:",
            values=[
                ("trust", f"Tool Trust Level (Current: {trust})"),
                ("comp", f"Compression Threshold (Current: {comp})"),
                ("url", f"Ollama URL (Current: {url})"),
                ("exit", "Exit Menu"),
            ]
        ).run_async()

        if choice == "exit" or choice is None:
            break

        if choice == "trust":
            new_trust = await radiolist_dialog(
                title="Trust Level",
                text="Select tool execution trust level:",
                values=[
                    ("none", "None (Ask for every tool)"),
                    ("partial", "Partial (Ask only for unsafe tools)"),
                    ("total", "Total (Never ask, full automatic)"),
                ]
            ).run_async()
            if new_trust:
                settings["trust_level"] = new_trust
                context.agent.trust_level = new_trust

        elif choice == "comp":
            new_comp = await input_dialog(
                title="Compression Threshold",
                text="Enter token threshold for history compression:"
            ).run_async()
            if new_comp and new_comp.isdigit():
                settings["compression_threshold"] = int(new_comp)
                context.config._parsed().compression_threshold = int(new_comp)

        elif choice == "url":
            new_url = await input_dialog(
                title="Ollama URL",
                text="Enter Ollama API URL:"
            ).run_async()
            if new_url:
                settings["url"] = new_url
                context.config._parsed().url = new_url
                context.agent.client.base_url = new_url

    settings_str = json.dumps(settings)
    update_profile_settings(context.database, profile.id, settings_str)
    profile.settings = settings_str
    await context.ui.on_system_message("[bold green]Settings saved.[/bold green]")
