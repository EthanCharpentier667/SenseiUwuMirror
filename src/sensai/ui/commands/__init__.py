"""Built-in slash commands for the CLI."""

from typing import TYPE_CHECKING

from sensai.ui.command import Command, CommandRegistry
from sensai.ui.commands.auth import logout_execute
from sensai.ui.commands.help import make_help_execute
from sensai.ui.commands.model import model_execute
from sensai.ui.commands.persona import persona_execute
from sensai.ui.commands.prefs import inst_execute, prefs_execute
from sensai.ui.commands.settings import settings_execute
from sensai.ui.commands.stat import stat_execute
from sensai.ui.commands.system import exit_execute
from sensai.ui.commands.tool import ToolNameCompleter, tool_execute

if TYPE_CHECKING:
    from sensai.agent import Agent


def setup_builtin_commands(registry: CommandRegistry, agent: "Agent | None" = None) -> None:
    """Register all built-in commands.

    Args:
        registry (CommandRegistry): The registry to add the commands to.
        agent (Agent | None): The agent whose tool names /tools completes. Default is
            None, which registers /tools without name completion.
    """
    registry.register(Command("/help", "List all available commands.", make_help_execute(registry)))
    registry.register(
        Command(
            "/tools",
            "Toggle tools in a dialog, /tools list, or /tools enable|disable <tool or group>...",
            tool_execute,
            subcommands=["list", "enable", "disable"],
            argument_completer=ToolNameCompleter(agent) if agent is not None else None,
        )
    )
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
    registry.register(Command("/stats", "Show statistics for the current session.", stat_execute))
    registry.register(
        Command("/model", "Change the AI model used in the current session.", model_execute)
    )
    registry.register(
        Command(
            "/persona",
            "List personas, or switch to one (saved to your profile).",
            persona_execute,
            subcommands=["list", "switch"],
        )
    )
