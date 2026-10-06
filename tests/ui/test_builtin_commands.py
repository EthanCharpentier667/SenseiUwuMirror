"""Tests for builtin commands."""

from sensai.ui.commands import setup_builtin_commands
from sensai.ui.command import CommandRegistry


def test_setup_builtin_commands() -> None:
    registry = CommandRegistry()
    setup_builtin_commands(registry)
    cmds = registry.get_all_commands()
    names = {c.name for c in cmds}
    assert "/help" in names
    assert "/logout" in names
    assert "/prefs" in names
    assert "/inst" in names
