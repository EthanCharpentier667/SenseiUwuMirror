"""Model command."""

from sensai.config import AVAILABLE_MODELS
from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import load_profile_settings, save_profile_settings
from sensai.ui.command import CommandContext

OTHER = "__other__"


async def prompt_for_model(context: CommandContext) -> str | None:
    """Let the user pick a known model, or type the name of any other Ollama model."""
    choice = await context.ui.prompt_choice(
        title="Model Selection",
        text=f"Choose an AI model (current: {context.agent.model}):",
        choices=[*((m, m) for m in AVAILABLE_MODELS), (OTHER, "Other…")],
    )
    if choice != OTHER:
        return choice
    name = await context.ui.prompt_input(title="Model", text="Enter the Ollama model name:")
    return name.strip() if name and name.strip() else None


async def warn_if_unknown_model(context: CommandContext, model_name: str) -> None:
    """Warn that a model isn't one of the known ones; Ollama may still serve it."""
    if model_name not in AVAILABLE_MODELS:
        await context.ui.on_system_message(
            f"[yellow]{model_name} is not in the known models ({', '.join(AVAILABLE_MODELS)}); "
            "make sure the Ollama server has it.[/yellow]"
        )


def _save_model_to_profile(context: CommandContext, model_name: str) -> None:
    profile = ProfileManager.current_profile
    if profile and profile.id:
        settings = load_profile_settings(profile)
        settings["model"] = model_name
        save_profile_settings(context.database, profile, settings)


async def model_execute(context: CommandContext, args: list[str]) -> None:
    """Execute the /model command."""
    model_name = args[0] if args else await prompt_for_model(context)
    if not model_name:
        return

    await warn_if_unknown_model(context, model_name)
    context.agent.model = model_name
    _save_model_to_profile(context, model_name)
    await context.ui.on_system_message(f"[bold green]Model updated to {model_name}![/bold green]")
