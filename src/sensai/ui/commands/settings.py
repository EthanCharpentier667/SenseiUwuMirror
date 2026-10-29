"""Settings command."""

import json
import math
from typing import Any

from sensai.config import DEFAULT_NUM_CTX
from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import update_profile_settings
from sensai.features.features import FEATURES
from sensai.ui.command import CommandContext
from sensai.ui.commands.tool import edit_tools


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


async def _handle_temperature_setting(settings: dict[str, Any], context: CommandContext) -> None:
    current = settings.get("temperature", context.agent.temperature)
    current_str = str(current) if current is not None else "default"
    new_temp = await context.ui.prompt_input(
        title="Temperature",
        text=(
            "Enter sampling temperature (float >= 0.0, or 'default' to clear, "
            f"current: {current_str}):"
        ),
    )
    if new_temp is None:
        return
    cleaned = new_temp.strip().lower()
    if cleaned in ("default", "none", "clear", ""):
        settings.pop("temperature", None)
        context.agent.temperature = None
        args = context.config.get_args()
        if args and hasattr(args, "temperature"):
            args.temperature = None
        return
    try:
        val = float(cleaned)
        if not math.isfinite(val) or val < 0.0:
            await context.ui.on_system_message(
                "[red]Temperature must be a finite, non-negative number.[/red]"
            )
            return
        settings["temperature"] = val
        context.agent.temperature = val
        args = context.config.get_args()
        if args and hasattr(args, "temperature"):
            args.temperature = val
    except ValueError:
        await context.ui.on_system_message(
            "[red]Invalid temperature format. Please enter a number.[/red]"
        )


async def _handle_top_p_setting(settings: dict[str, Any], context: CommandContext) -> None:
    current = settings.get("top_p", context.agent.top_p)
    current_str = str(current) if current is not None else "default"
    new_top_p = await context.ui.prompt_input(
        title="Top P",
        text=(
            "Enter nucleus sampling top_p (0.0 to 1.0, or 'default' to clear, "
            f"current: {current_str}):"
        ),
    )
    if new_top_p is None:
        return
    cleaned = new_top_p.strip().lower()
    if cleaned in ("default", "none", "clear", ""):
        settings.pop("top_p", None)
        context.agent.top_p = None
        args = context.config.get_args()
        if args and hasattr(args, "top_p"):
            args.top_p = None
        return
    try:
        val = float(cleaned)
        if not (0.0 <= val <= 1.0):
            await context.ui.on_system_message("[red]Top P must be between 0.0 and 1.0.[/red]")
            return
        settings["top_p"] = val
        context.agent.top_p = val
        args = context.config.get_args()
        if args and hasattr(args, "top_p"):
            args.top_p = val
    except ValueError:
        await context.ui.on_system_message(
            "[red]Invalid Top P format. Please enter a number.[/red]"
        )


async def _handle_num_ctx_setting(settings: dict[str, Any], context: CommandContext) -> None:
    current = settings.get("num_ctx", context.agent.num_ctx)
    current_str = str(current) if current is not None else "default"
    new_num_ctx = await context.ui.prompt_input(
        title="Context Length",
        text=(
            "Enter context length in tokens (integer > 0, or 'default' to clear, "
            f"current: {current_str}):"
        ),
    )
    if new_num_ctx is None:
        return
    cleaned = new_num_ctx.strip().lower()
    if cleaned in ("default", "none", "clear", ""):
        settings.pop("num_ctx", None)
        context.agent.num_ctx = DEFAULT_NUM_CTX
        args = context.config.get_args()
        if args and hasattr(args, "num_ctx"):
            args.num_ctx = DEFAULT_NUM_CTX
        return
    if cleaned.isdigit() and int(cleaned) > 0:
        val = int(cleaned)
        settings["num_ctx"] = val
        context.agent.num_ctx = val
        args = context.config.get_args()
        if args and hasattr(args, "num_ctx"):
            args.num_ctx = val
    else:
        await context.ui.on_system_message(
            "[red]Invalid context length. Please enter a positive integer.[/red]"
        )


async def _handle_features_setting(settings: dict[str, Any], context: CommandContext) -> None:
    features = context.config.features
    while True:
        choice = await context.ui.prompt_choice(
            title="Features",
            text="Select a feature to enable or disable:",
            choices=[
                *(
                    (name, f"{name} [{'on' if features.is_enabled(name) else 'off'}]: {help_}")
                    for name, help_ in FEATURES.items()
                ),
                ("back", "Back"),
            ],
        )
        if choice == "back" or choice is None:
            break
        features.toggle(choice)
    settings["disabled_features"] = sorted(features.disabled)


async def _handle_tools_setting(settings: dict[str, Any], context: CommandContext) -> None:
    if await edit_tools(context):
        settings["disabled_tools"] = sorted(context.config.features.disabled_tools)
        settings["disabled_features"] = sorted(context.config.features.disabled)


async def _prompt_settings_menu(context: CommandContext, settings: dict[str, Any]) -> str | None:
    trust = settings.get("trust_level", context.agent.trust_level)
    comp = settings.get("compression_threshold", context.config.compression_threshold)
    url = settings.get("url", context.config.url)
    disabled = ", ".join(sorted(context.config.features.disabled)) or "none"
    disabled_tools = ", ".join(sorted(context.config.features.disabled_tools)) or "none"
    temp = settings.get("temperature", context.agent.temperature)
    top_p = settings.get("top_p", context.agent.top_p)
    num_ctx = settings.get("num_ctx", context.agent.num_ctx)
    temp_display = temp if temp is not None else "default"
    top_p_display = top_p if top_p is not None else "default"
    num_ctx_display = num_ctx if num_ctx is not None else "default"

    return await context.ui.prompt_choice(
        title="Settings Menu",
        text="Choose a setting to modify:",
        choices=[
            ("trust", f"Tool Trust Level (Current: {trust})"),
            ("comp", f"Compression Threshold (Current: {comp})"),
            ("url", f"Ollama URL (Current: {url})"),
            ("temperature", f"Temperature (Current: {temp_display})"),
            ("top_p", f"Top P (Current: {top_p_display})"),
            ("num_ctx", f"Context Length (Current: {num_ctx_display})"),
            ("features", f"Features (Disabled: {disabled})"),
            ("tools", f"Tools (Disabled: {disabled_tools})"),
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
    elif choice == "temperature":
        await _handle_temperature_setting(settings, context)
    elif choice == "top_p":
        await _handle_top_p_setting(settings, context)
    elif choice == "num_ctx":
        await _handle_num_ctx_setting(settings, context)
    elif choice == "features":
        await _handle_features_setting(settings, context)
    elif choice == "tools":
        await _handle_tools_setting(settings, context)


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
