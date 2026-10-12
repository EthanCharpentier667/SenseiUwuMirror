"""Tests for inserting MCP JSON configurations through the CLI completer."""

import asyncio
import shlex
from typing import Any
from unittest.mock import Mock

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from sensai.agent import Agent
from sensai.mcp.mcp_server_config import MCPServerConfig
from sensai.ui.app import CLIApp
from sensai.ui.command import CommandRegistry
from sensai.ui.commands.mcp.mcp_commands import MCPCommands


@pytest.fixture
def registry() -> CommandRegistry:
    registry = CommandRegistry()
    MCPCommands(Mock(spec=Agent)).register(registry)
    return registry


@pytest.mark.parametrize("prefix", ["", "'", "'{", "{", '"{', '\'{"url": '])
def test_templates_insert_valid_quoted_json(registry: CommandRegistry, prefix: str) -> None:
    text = f"/mcp add-json server {prefix}"
    document = Document(text)
    completions = list(registry.get_completer().get_completions(document, CompleteEvent()))

    assert [completion.display_text for completion in completions] == [
        "HTTP",
        "HTTP + Bearer token",
        "HTTP + OAuth",
    ]
    for completion in completions:
        buffer = Buffer(document=document)
        buffer.apply_completion(completion)
        args = shlex.split(buffer.text)
        assert args[:3] == ["/mcp", "add-json", "server"]
        assert len(args) == 4
        config = MCPServerConfig.from_json(args[3])
        assert config.url == "https://example.com/mcp"
        if completion.display_text == "HTTP + Bearer token":
            assert config.headers == {"Authorization": "Bearer YOUR_TOKEN"}
            assert config.oauth is None
        elif completion.display_text == "HTTP + OAuth":
            assert config.oauth is not None
            assert config.oauth.metadata.redirect_uris is not None
            assert (
                str(config.oauth.metadata.redirect_uris[0])
                == "https://your-callback.example/callback"
            )
            assert config.headers == {}
        else:
            assert config.headers == {}
            assert config.oauth is None


@pytest.mark.parametrize("name", ["server", "'my server'", '"my server"', r"my\ server"])
def test_completion_preserves_name_and_spacing(registry: CommandRegistry, name: str) -> None:
    document = Document(f"/mcp  add-json  {name}   ")
    completion = next(registry.get_completer().get_completions(document, CompleteEvent()))
    buffer = Buffer(document=document)
    buffer.apply_completion(completion)

    assert buffer.text.startswith(document.text)
    assert shlex.split(buffer.text)[2] == shlex.split(name)[0]


@pytest.mark.parametrize(
    "text",
    [
        "/mcp add-json ",
        "/mcp add-json server",
        "/mcp other server ",
        "/mcp add-json 'unfinished name ",
        '/mcp add-json "unfinished name ',
        "/mcp add-json '   ' ",
        '/mcp add-json server \'{"url": "https://my-server/mcp"',
    ],
)
def test_no_template_overwrites_personalized_input(registry: CommandRegistry, text: str) -> None:
    completions = list(registry.get_completer().get_completions(Document(text), CompleteEvent()))
    assert completions == []


def test_templates_do_not_replace_json_in_middle_of_input(registry: CommandRegistry) -> None:
    text = '/mcp add-json server \'{"url": "https://my-server/mcp"}\''
    cursor = text.index("{") + 1
    completions = list(
        registry.get_completer().get_completions(Document(text, cursor), CompleteEvent())
    )
    assert completions == []


@pytest.mark.parametrize("text", ["/mcp a", "/mcp add-json"])
def test_mcp_subcommand_completion_still_works(registry: CommandRegistry, text: str) -> None:
    completions = list(registry.get_completer().get_completions(Document(text), CompleteEvent()))
    assert [completion.text for completion in completions] == ["add-json"]


@pytest.mark.asyncio
async def test_tab_then_enter_accepts_template_before_submitting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TERM", "xterm-256color")
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        app = CLIApp(
            agent=Mock(spec=Agent, tools=[]),
            database=Mock(),
            session=Mock(),
            client=Mock(),
            config=Mock(),
            profile_name="Test",
            embedder=Mock(),
        )
        assert app.prompt_session is not None
        buffer = app.prompt_session.default_buffer
        ready = asyncio.Event()
        accepted = asyncio.Event()

        def on_completions(buffer: Buffer) -> None:
            if buffer.complete_state is not None and buffer.complete_state.completions:
                ready.set()

        buffer.on_completions_changed += on_completions

        def on_update(_application: Any) -> None:
            if buffer.complete_state is None and buffer.text.endswith("}'"):
                accepted.set()

        app.prompt_session.app.after_render += on_update
        prompt = asyncio.create_task(app.prompt_session.prompt_async())
        try:
            pipe.send_text("/mcp add-json local \t")
            await asyncio.wait_for(ready.wait(), timeout=2)
            pipe.send_text("\x1b[B\r")
            await asyncio.wait_for(accepted.wait(), timeout=2)
            assert not prompt.done()
            edited = buffer.text.replace("https://example.com/mcp", "http://localhost:8000/mcp")
            config = MCPServerConfig.from_json(shlex.split(edited)[3])
            assert config.url == "http://localhost:8000/mcp"

            pipe.send_text("\x01\x0b" + edited + "\r")
            assert await asyncio.wait_for(prompt, timeout=2) == edited
        finally:
            prompt.cancel()
            await asyncio.gather(prompt, return_exceptions=True)
