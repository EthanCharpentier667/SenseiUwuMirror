"""Human-in-the-loop approval gate for tool calls."""

import json
from typing import Any


def _display_tool_call(name: str, arguments: dict[str, Any]) -> None:
    """Print the tool name and arguments to stdout.

    Args:
        name: The name of the tool about to be called.
        arguments: The arguments that will be passed to the tool.
    """
    print(f"\nThe AI wants to call '{name}' with the following arguments:")  # noqa: T201
    print(json.dumps(arguments, indent=2, ensure_ascii=False))  # noqa: T201


def _get_user_choice() -> str:
    """Prompt the user for a confirmation choice.

    Returns:
        The raw user input, stripped and lowercased.
    """
    return input("Approve? [y/n] : ").strip().lower()


def require_approval(name: str, arguments: dict[str, Any]) -> bool:
    """Ask the user to approve a tool call before it is executed.

    Displays the tool name and its arguments, then waits for the user
    to confirm or deny execution.

    Args:
        name: The name of the tool about to be called.
        arguments: The arguments that will be passed to the tool.

    Returns:
        True if the user approves, False otherwise.
    """
    _display_tool_call(name, arguments)
    choice = _get_user_choice()
    return choice in {"y", "yes", "o", "oui", ""}
