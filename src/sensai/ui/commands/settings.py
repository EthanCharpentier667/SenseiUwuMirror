"""Settings command."""

import json
from typing import Any

from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import update_profile_settings
from sensai.ui.command import CommandContext


async def _handle_trust_setting(settings: dict[str, Any], context: CommandContext) -> None:
    new_trust = await context.ui.prompt_choice(
        title="Trust Level",
        text="Select tool execution trust level:",
        choices=[
            ("none", "None (Ask for every tool)"),
            ("partial", "Partial (Ask only for unsafe tools)"),
            ("total", "Total (Never ask, full automatic)"),
        ],
    )
    if new_trust:
        settings["trust_level"] = new_trust
        context.agent.trust_level = new_trust


async def _handle_comp_setting(settings: dict[str, Any], context: CommandContext) -> None:
    new_comp = await context.ui.prompt_input(
        title="Compression Threshold", text="Enter token threshold for history compression:"
    )
    if new_comp and new_comp.isdigit():
        settings["compression_threshold"] = int(new_comp)
        args = context.config.get_args()
        if args:
            args.compression_threshold = int(new_comp)


async def _handle_url_setting(settings: dict[str, Any], context: CommandContext) -> None:
    new_url = await context.ui.prompt_input(title="Ollama URL", text="Enter Ollama API URL:")
    if new_url:
        if not new_url.endswith("/api/chat"):
            new_url = new_url.rstrip("/") + "/api/chat"
        settings["url"] = new_url
        args = context.config.get_args()
        if args:
            args.url = new_url
        context.agent.client.base_url = new_url


async def _prompt_settings_menu(context: CommandContext, settings: dict[str, Any]) -> str | None:
    trust = settings.get("trust_level", context.agent.trust_level)
    comp = settings.get("compression_threshold", context.config.compression_threshold)
    url = settings.get("url", context.config.url)

    return await context.ui.prompt_choice(
        title="Settings Menu",
        text="Choose a setting to modify:",
        choices=[
            ("trust", f"Tool Trust Level (Current: {trust})"),
            ("comp", f"Compression Threshold (Current: {comp})"),
            ("url", f"Ollama URL (Current: {url})"),
            ("exit", "Exit Menu"),
        ],
    )


async def _process_settings_choice(
    choice: str, settings: dict[str, Any], context: CommandContext
) -> None:
    if choice == "trust":
        await _handle_trust_setting(settings, context)
    elif choice == "comp":
        await _handle_comp_setting(settings, context)
    elif choice == "url":
        await _handle_url_setting(settings, context)


def _save_settings_to_profile(
    context: CommandContext, settings: dict[str, Any], profile_id: int
) -> str:
    settings_str = json.dumps(settings)
    update_profile_settings(context.database, profile_id, settings_str)
    return settings_str


async def settings_execute(context: CommandContext, _args: list[str]) -> None:
    """Execute the /settings command."""
    profile = ProfileManager.current_profile
    if not profile or not profile.id:
        await context.ui.on_system_message("[red]No active profile found.[/red]")
        return

    try:
        settings = json.loads(profile.settings) if profile.settings else {}
    except json.JSONDecodeError:
        settings = {}

    while True:
        choice = await _prompt_settings_menu(context, settings)

        if choice == "exit" or choice is None:
            break

        await _process_settings_choice(choice, settings, context)

    profile.settings = _save_settings_to_profile(context, settings, profile.id)
    await context.ui.on_system_message("[bold green]Settings saved.[/bold green]")
