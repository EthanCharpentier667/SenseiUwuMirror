"""Model command."""

import json

from sensai.config import AVAILABLE_MODELS
from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import update_profile_settings
from sensai.ui.command import CommandContext


async def model_execute(context: CommandContext, args: list[str]) -> None:
    """Execute the /model command."""
    if not args:
        choice = await context.ui.prompt_choice(
            title="Model Selection",
            text="Choose an AI model:",
            choices=[(m, m) for m in AVAILABLE_MODELS],
        )

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

    context.agent.model = model_name
    await context.ui.on_system_message(f"[bold green]Model updated to {model_name}![/bold green]")

    profile = ProfileManager.current_profile
    if profile and profile.id:
        settings = json.loads(profile.settings) if profile.settings else {}
        settings["model"] = model_name
        settings_str = json.dumps(settings)
        update_profile_settings(context.database, profile.id, settings_str)
        profile.settings = settings_str
