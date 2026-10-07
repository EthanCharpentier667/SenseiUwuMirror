"""Model command."""

import json

from sensai.config import AVAILABLE_MODELS
from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import update_profile_settings
from sensai.ui.command import CommandContext


async def _prompt_for_model(context: CommandContext) -> str | None:
    return await context.ui.prompt_choice(
        title="Model Selection",
        text="Choose an AI model:",
        choices=[(m, m) for m in AVAILABLE_MODELS],
    )


async def _apply_model_to_context(context: CommandContext, model_name: str) -> None:
    context.agent.model = model_name
    await context.ui.on_system_message(f"[bold green]Model updated to {model_name}![/bold green]")


def _save_model_to_profile(context: CommandContext, model_name: str) -> None:
    profile = ProfileManager.current_profile
    if profile and profile.id:
        try:
            settings = json.loads(profile.settings) if profile.settings else {}
        except json.JSONDecodeError:
            settings = {}
        settings["model"] = model_name
        settings_str = json.dumps(settings)
        update_profile_settings(context.database, profile.id, settings_str)
        profile.settings = settings_str


async def model_execute(context: CommandContext, args: list[str]) -> None:
    """Execute the /model command."""
    if not args:
        choice = await _prompt_for_model(context)
        if not choice:
            return
        args = [choice]

    model_name = args[0]
    if model_name not in AVAILABLE_MODELS:
        available_str = ", ".join(AVAILABLE_MODELS)
        await context.ui.on_system_message(
            f"[bold red]Unknown model: {model_name}. Available: {available_str}[/bold red]"
        )
        return

    await _apply_model_to_context(context, model_name)
    _save_model_to_profile(context, model_name)
