"""Settings command."""

import math
from typing import Any
from urllib.parse import urlparse

from sensai.config import TRUST_LEVELS
from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import load_profile_settings, save_profile_settings
from sensai.features.features import FEATURES
from sensai.ui.command import CommandContext
from sensai.ui.commands.model import prompt_for_model, warn_if_unknown_model
from sensai.ui.commands.tool import edit_tools

RESET_WORDS = ("default", "none", "clear", "")


def _set_arg(context: CommandContext, name: str, value: Any) -> None:
    """Mirror a setting into the parsed arguments, which the rest of the app reads."""
    args = context.config.get_args()
    if args and hasattr(args, name):
        setattr(args, name, value)


async def _handle_trust_setting(settings: dict[str, Any], context: CommandContext) -> None:
    labels = {
        "none": "None (Ask for every tool)",
        "partial": "Partial (Ask only for unsafe tools)",
        "total": "Total (Never ask, full automatic)",
    }
    new_trust = await context.ui.prompt_choice(
        title="Trust Level",
        text="Select tool execution trust level:",
        choices=[(level, labels[level]) for level in TRUST_LEVELS],
    )
    if new_trust:
        settings["trust_level"] = new_trust
        context.agent.trust_level = new_trust


async def _handle_model_setting(settings: dict[str, Any], context: CommandContext) -> None:
    model_name = await prompt_for_model(context)
    if model_name:
        await warn_if_unknown_model(context, model_name)
        settings["model"] = model_name
        context.agent.model = model_name


async def _handle_comp_setting(settings: dict[str, Any], context: CommandContext) -> None:
    new_comp = await context.ui.prompt_input(
        title="Compression Threshold",
        text=(
            "Enter token threshold for history compression "
            f"(current: {context.config.compression_threshold}):"
        ),
    )
    if new_comp is None:
        return
    cleaned = new_comp.strip()
    if not cleaned.isdigit() or int(cleaned) <= 0:
        await context.ui.on_system_message(
            "[red]Invalid compression threshold. Please enter a positive integer.[/red]"
        )
        return
    settings["compression_threshold"] = int(cleaned)
    _set_arg(context, "compression_threshold", int(cleaned))


async def _keep_token_for(context: CommandContext, new_url: str) -> bool:
    """Whether to keep sending the bearer token once the chat URL is ``new_url``.

    The token is only asked about when it would reach another host than before.
    """
    client = context.agent.client
    if not client.token or urlparse(new_url).hostname == urlparse(client.base_url).hostname:
        return True
    choice = await context.ui.prompt_choice(
        title="API Token",
        text=f"Send the current API token to {urlparse(new_url).hostname} too?",
        choices=[("drop", "No, stop sending it (safer)"), ("keep", "Yes, keep sending it")],
    )
    return choice == "keep"


async def _handle_url_setting(settings: dict[str, Any], context: CommandContext) -> None:
    new_url = await context.ui.prompt_input(
        title="Ollama URL", text=f"Enter Ollama API URL (current: {context.config.url}):"
    )
    if not new_url or not new_url.strip():
        return
    new_url = new_url.strip()
    parsed = urlparse(new_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        await context.ui.on_system_message(
            "[red]Invalid URL. Use http(s)://host[:port], e.g. http://localhost:11434.[/red]"
        )
        return
    if not new_url.endswith("/api/chat"):
        new_url = new_url.rstrip("/") + "/api/chat"
    keep_token = await _keep_token_for(context, new_url)
    if not keep_token:
        context.agent.client.token = None
    settings["url"] = new_url
    settings["send_token"] = keep_token
    _set_arg(context, "url", new_url)
    context.agent.client.base_url = new_url


async def _handle_timeout_setting(settings: dict[str, Any], context: CommandContext) -> None:
    new_timeout = await context.ui.prompt_input(
        title="Request Timeout",
        text=(
            "Enter the Ollama request timeout in seconds (number > 0, or 'default' to clear, "
            f"current: {context.agent.client.timeout}):"
        ),
    )
    if new_timeout is None:
        return
    cleaned = new_timeout.strip().lower()
    if cleaned in RESET_WORDS:
        settings.pop("timeout", None)
        val = float(context.config.startup_value("timeout"))
    else:
        try:
            val = float(cleaned)
        except ValueError:
            val = math.nan
        if not math.isfinite(val) or val <= 0.0:
            await context.ui.on_system_message(
                "[red]Invalid timeout. Please enter a positive number of seconds.[/red]"
            )
            return
        settings["timeout"] = val
    context.agent.client.timeout = val
    _set_arg(context, "timeout", val)


async def _handle_max_steps_setting(settings: dict[str, Any], context: CommandContext) -> None:
    new_steps = await context.ui.prompt_input(
        title="ReAct Max Steps",
        text=(
            "Enter the maximum ReAct steps per reply (integer > 0, or 'default' to clear, "
            f"current: {context.agent.max_turns}):"
        ),
    )
    if new_steps is None:
        return
    cleaned = new_steps.strip().lower()
    if cleaned in RESET_WORDS:
        settings.pop("max_steps", None)
        context.agent.max_turns = int(context.config.startup_value("max_steps"))
    elif cleaned.isdigit() and int(cleaned) > 0:
        settings["max_steps"] = int(cleaned)
        context.agent.max_turns = int(cleaned)
    else:
        await context.ui.on_system_message(
            "[red]Invalid max steps. Please enter a positive integer.[/red]"
        )


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
    if cleaned in RESET_WORDS:
        settings.pop("temperature", None)
        context.agent.temperature = context.config.startup_value("temperature")
        _set_arg(context, "temperature", context.agent.temperature)
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
        _set_arg(context, "temperature", val)
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
    if cleaned in RESET_WORDS:
        settings.pop("top_p", None)
        context.agent.top_p = context.config.startup_value("top_p")
        _set_arg(context, "top_p", context.agent.top_p)
        return
    try:
        val = float(cleaned)
        if not (0.0 <= val <= 1.0):
            await context.ui.on_system_message("[red]Top P must be between 0.0 and 1.0.[/red]")
            return
        settings["top_p"] = val
        context.agent.top_p = val
        _set_arg(context, "top_p", val)
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
    if cleaned in RESET_WORDS:
        settings.pop("num_ctx", None)
        context.agent.num_ctx = context.config.startup_value("num_ctx")
        _set_arg(context, "num_ctx", context.agent.num_ctx)
        return
    if cleaned.isdigit() and int(cleaned) > 0:
        val = int(cleaned)
        settings["num_ctx"] = val
        context.agent.num_ctx = val
        _set_arg(context, "num_ctx", val)
    else:
        await context.ui.on_system_message(
            "[red]Invalid context length. Please enter a positive integer.[/red]"
        )


async def _handle_features_setting(settings: dict[str, Any], context: CommandContext) -> None:
    features = context.config.features
    result = await context.ui.prompt_checklist(
        title="Features",
        text="Tick the features to enable:",
        choices=[(name, f"{name}: {help_}") for name, help_ in FEATURES.items()],
        checked=[name for name in FEATURES if features.is_enabled(name)],
    )
    if result is None:
        return
    _, ticked = result
    for name in FEATURES:
        if features.is_enabled(name) != (name in ticked):
            features.set(name, enabled=name in ticked)
    settings["disabled_features"] = sorted(features.saved_disabled)


async def _handle_tools_setting(settings: dict[str, Any], context: CommandContext) -> None:
    if not context.agent.tools:
        await context.ui.on_system_message("No tools available.")
        return
    if await edit_tools(context, save=False):
        settings["disabled_tools"] = sorted(context.config.features.saved_disabled_tools)


HANDLERS = {
    "trust": _handle_trust_setting,
    "model": _handle_model_setting,
    "comp": _handle_comp_setting,
    "url": _handle_url_setting,
    "timeout": _handle_timeout_setting,
    "max_steps": _handle_max_steps_setting,
    "temperature": _handle_temperature_setting,
    "top_p": _handle_top_p_setting,
    "num_ctx": _handle_num_ctx_setting,
    "features": _handle_features_setting,
    "tools": _handle_tools_setting,
}


def _display(value: Any) -> Any:
    return value if value is not None else "default"


async def _prompt_settings_menu(context: CommandContext) -> str | None:
    agent = context.agent
    disabled = ", ".join(sorted(context.config.features.disabled)) or "none"
    disabled_tools = ", ".join(sorted(context.config.features.disabled_tools)) or "none"

    return await context.ui.prompt_choice(
        title="Settings Menu",
        text="Choose a setting to modify:",
        choices=[
            ("trust", f"Tool Trust Level (Current: {agent.trust_level})"),
            ("model", f"Model (Current: {agent.model})"),
            ("comp", f"Compression Threshold (Current: {context.config.compression_threshold})"),
            ("url", f"Ollama URL (Current: {context.config.url})"),
            ("timeout", f"Request Timeout (Current: {agent.client.timeout}s)"),
            ("max_steps", f"ReAct Max Steps (Current: {agent.max_turns})"),
            ("temperature", f"Temperature (Current: {_display(agent.temperature)})"),
            ("top_p", f"Top P (Current: {_display(agent.top_p)})"),
            ("num_ctx", f"Context Length (Current: {_display(agent.num_ctx)})"),
            ("features", f"Features (Disabled: {disabled})"),
            ("tools", f"Tools (Disabled: {disabled_tools})"),
            ("exit", "Exit Menu"),
        ],
    )


async def settings_execute(context: CommandContext, _args: list[str]) -> None:
    """Execute the /settings command.

    Every change takes effect at once and is saved to the profile right away.
    """
    profile = ProfileManager.current_profile
    if not profile or not profile.id:
        await context.ui.on_system_message("[red]No active profile found.[/red]")
        return

    changed = False
    while True:
        choice = await _prompt_settings_menu(context)
        handler = HANDLERS.get(choice or "")
        if handler is None:
            break
        settings = load_profile_settings(profile)
        before = dict(settings)
        await handler(settings, context)
        if settings != before:
            save_profile_settings(context.database, profile, settings)
            changed = True

    if changed:
        await context.ui.on_system_message("[bold green]Settings saved.[/bold green]")
