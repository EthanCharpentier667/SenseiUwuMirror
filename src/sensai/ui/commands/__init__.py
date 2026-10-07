"""Built-in slash commands for the CLI."""

from sensai.ui.command import Command, CommandRegistry
from sensai.ui.commands.auth import logout_execute
from sensai.ui.commands.help import help_execute
from sensai.ui.commands.model import model_execute
from sensai.ui.commands.prefs import inst_execute, prefs_execute
from sensai.ui.commands.settings import settings_execute
from sensai.ui.commands.system import exit_execute


def setup_builtin_commands(registry: CommandRegistry) -> None:
    """Register all built-in commands."""
    registry.register(Command("/help", "List all available commands.", help_execute))
    registry.register(Command("/logout", "Log out and clear saved credentials.", logout_execute))
    registry.register(Command("/exit", "Exit the application.", exit_execute))
    registry.register(Command("/quit", "Exit the application.", exit_execute))
    registry.register(
        Command(
            "/prefs",
            "Manage preferences.",
            prefs_execute,
            subcommands=["list", "add", "remove", "edit"],
        )
    )
    registry.register(
        Command(
            "/inst",
            "Manage system instructions.",
            inst_execute,
            subcommands=["list", "add", "remove", "edit"],
        )
    )
    registry.register(Command("/settings", "Open interactive settings menu.", settings_execute))
    registry.register(
        Command("/model", "Change the AI model used in the current session.", model_execute)
    )
