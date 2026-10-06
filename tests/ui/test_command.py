"""Tests for the command registry."""

from typing import Any

import pytest

from sensai.ui.command import Command, CommandRegistry


@pytest.mark.asyncio
async def test_command_registry() -> None:
    registry = CommandRegistry()
    calls = []

    async def _test_cmd(app: Any, args: list[str]) -> None:
        calls.append(args)

    cmd = Command("/test", "A test command", _test_cmd)
    registry.register(cmd)

    assert len(registry.get_all_commands()) == 1

    # Execute
    class MockUIHandler:
        async def on_system_message(self, message: Any) -> None:
            pass

        async def on_error(self, error: Exception) -> None:
            pass

    from sensai.ui.command import CommandContext  # noqa: PLC0415

    ctx = CommandContext(database=None, ui=MockUIHandler(), agent=None, config=None, session=None)  # type: ignore[arg-type]

    await registry.execute("/test arg1 arg2", ctx)

    assert calls == [["arg1", "arg2"]]

    # Unknown command
    await registry.execute("/unknown", ctx)
    assert len(calls) == 1


def test_slash_command_completer() -> None:
    from prompt_toolkit.completion import CompleteEvent  # noqa: PLC0415
    from prompt_toolkit.document import Document  # noqa: PLC0415

    from sensai.ui.command import SlashCommandCompleter  # noqa: PLC0415

    async def dummy_cmd(c: Any, a: Any) -> None:
        pass

    cmd1 = Command("/test", "Test 1", dummy_cmd, subcommands=["add", "remove"])
    cmd2 = Command("/taco", "Test 2", dummy_cmd)

    completer = SlashCommandCompleter({"/test": cmd1, "/taco": cmd2})
    event = CompleteEvent()

    # Not starting with slash
    comps = list(completer.get_completions(Document("hello"), event))
    assert len(comps) == 0

    # Starting with slash, matching multiple
    comps = list(completer.get_completions(Document("/t"), event))
    assert len(comps) == 2
    assert {c.text for c in comps} == {"/test", "/taco"}

    # Subcommand completion
    comps = list(completer.get_completions(Document("/test a"), event))
    assert len(comps) == 1
    assert comps[0].text == "add"

    # Subcommand completion empty match
    comps = list(completer.get_completions(Document("/taco a"), event))
    assert len(comps) == 0
