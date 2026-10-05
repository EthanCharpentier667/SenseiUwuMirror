"""Tests for the ``sensai`` package entry point."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Self

import pytest
from mcp.types import Tool as MCPToolDefinition

from sensai import main
from sensai.agent import Agent
from sensai.client import OllamaClient, Response
from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import Profile
from sensai.data.session.session import Session
from sensai.tools.mcp_tools import MCPTools
from sensai.tools.temperature_example import TempToolExample
from sensai.tools.web_search import WebSearch


def _make_response(text: str = "This is a mock response.") -> Response:
    return Response(
        response=text,
        respond_time=0.0,
        request_time=0.0,
        total_duration=0,
        model="llama3.2",
        tools=[],
        messages=[],
        prompt_eval_count=0,
        eval_count=0,
        token_used=0,
        status_code=200,
        tool_calls=[],
        stop_reason="stop",
    )


def _make_session() -> Session:
    return Session(profile_id=1, name="test_session", id=1)


def _make_profile(*_args: Any, **_kwargs: Any) -> Profile:
    profile = Profile(name="Default Profile", password="hashed", id=1)  # noqa: S106
    ProfileManager.current_profile = profile
    return profile


class _FakeDatabase:
    """Stand-in for Database that never touches disk."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def initialize(self) -> None:
        pass


class _FakeMCPClient:
    """Track one MCP connection and its tool discovery."""

    def __init__(self) -> None:
        self.connected = False
        self.closed = False
        self.listed = 0

    def activate(self) -> Self:
        """Return the context entered by the refactored MCP clients."""
        return self

    async def __aenter__(self) -> Self:
        self.connected = True
        return self

    async def __aexit__(self, *_args: object) -> None:
        self.connected = False
        self.closed = True

    async def list_tools(self) -> SimpleNamespace:
        assert self.connected
        self.listed += 1
        return SimpleNamespace(
            tools=[
                MCPToolDefinition(
                    name="remote_add",
                    description="Add two numbers.",
                    input_schema={"type": "object", "properties": {}},
                )
            ]
        )


async def _fake_retrieve_chunks(*_args: Any, **_kwargs: Any) -> list[Any]:
    return []


async def _fake_maybe_compress_session(*_args: Any, **_kwargs: Any) -> Session:
    return _make_session()


def _patch_main_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _mock_auth(*args: Any, **kwargs: Any) -> Profile:
        return _make_profile()

    monkeypatch.setattr("sys.argv", ["sensai"])
    monkeypatch.setattr("sensai.setup_database", lambda *args, **kwargs: _FakeDatabase())
    monkeypatch.setattr("sensai.authenticate_user", _mock_auth)
    monkeypatch.setattr("sensai.get_or_create_session", lambda *args, **kwargs: _make_session())
    monkeypatch.setattr("sensai.ui.app.update_session", lambda *args, **kwargs: _make_session())
    monkeypatch.setattr("sensai.ui.app.maybe_compress_session", _fake_maybe_compress_session)
    monkeypatch.setattr("sensai.ui.app.retrieve_chunks", _fake_retrieve_chunks)


def _assert_agent_calls(calls: list[dict[str, Any]], expected_route: str | None) -> None:
    """Check the messages and tools supplied on each turn."""
    assert len(calls) == 2
    for call, text in zip(calls, ["hello there", "second question"], strict=True):
        assert call["prompt"] is None
        assert call["messages"] == [{"role": "user", "content": text}]
        tools = call["tools"]
        assert len(tools) == (4 if expected_route else 3)
        assert isinstance(tools[0], WebSearch)
        assert isinstance(tools[1], TempToolExample)
        if expected_route:
            assert isinstance(tools[-1], MCPTools)
            assert tools[-1].name == "remote_add"


@pytest.mark.parametrize(
    ("mode", "expected_route"),
    [
        ("local", None),
        ("github", "github"),
        ("public", "public"),
        ("github_without_token", "public"),
    ],
)
def test_main_calls_agent_run_for_each_input(
    monkeypatch: pytest.MonkeyPatch, mode: str, expected_route: str | None
) -> None:
    """Each turn uses local tools and any MCP connection selected by the flags."""
    calls: list[dict[str, Any]] = []
    clients: list[_FakeMCPClient] = []
    routes: list[str] = []
    server_url = "https://docs.mcp.cloudflare.com/mcp"

    def fake_github_client() -> _FakeMCPClient:
        routes.append("github")
        client = _FakeMCPClient()
        clients.append(client)
        return client

    def fake_public_client(url: str) -> _FakeMCPClient:
        assert url == server_url
        routes.append("public")
        client = _FakeMCPClient()
        clients.append(client)
        return client

    async def mock_run(
        self: Agent,
        prompt: str | None = None,
        *,
        messages: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
    ) -> Response:
        calls.append({"prompt": prompt, "messages": messages, "tools": list(self.tools)})
        assert isinstance(self.client, OllamaClient)
        assert self.model == "llama3.2"
        assert self.human_in_the_loop is True
        if expected_route is not None:
            assert clients[-1].connected
            assert not clients[-1].closed
        return _make_response()

    inputs = iter(["hello there", "second question"])

    async def fake_prompt_async(*args: Any, **kwargs: Any) -> str:
        try:
            return next(inputs)
        except StopIteration as exc:
            raise EOFError from exc

    _patch_main_dependencies(monkeypatch)
    monkeypatch.setattr("sensai.USE_MCP_MODE", mode != "local")
    monkeypatch.setattr("sensai.USE_GITHUB_MCP", mode in {"github", "github_without_token"})
    monkeypatch.setattr("sensai.MCP_SERVER_URL", server_url)
    monkeypatch.delenv("GITHUB_MCP_TOKEN", raising=False)
    if mode == "github":
        monkeypatch.setenv("GITHUB_MCP_TOKEN", "test-token")
    monkeypatch.setattr("sensai.GitHubMCP", fake_github_client)
    monkeypatch.setattr("sensai.SensAIClient", fake_public_client)
    monkeypatch.setattr(Agent, "run", mock_run)
    monkeypatch.setattr("sensai.ui.app.PromptSession.prompt_async", fake_prompt_async)

    main()

    assert routes == ([expected_route] if expected_route else [])
    assert len(clients) == (1 if expected_route else 0)
    assert all(client.closed and not client.connected and client.listed == 1 for client in clients)
    _assert_agent_calls(calls, expected_route)


def test_main_combines_retrieved_context_with_mcp_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """An MCP-enabled turn receives RAG excerpts and the next turn sees the updated session."""
    _patch_main_dependencies(monkeypatch)
    monkeypatch.setattr("sensai.USE_MCP_MODE", True)
    monkeypatch.setattr("sensai.USE_GITHUB_MCP", True)
    monkeypatch.setenv("GITHUB_MCP_TOKEN", "test-token")
    clients: list[_FakeMCPClient] = []

    def fake_github_client() -> _FakeMCPClient:
        client = _FakeMCPClient()
        clients.append(client)
        return client

    updated_session = _make_session()

    async def keep_updated_session(
        _database: Any, session: Session, *_args: Any, **_kwargs: Any
    ) -> Session:
        return session

    monkeypatch.setattr("sensai.ui.app.maybe_compress_session", keep_updated_session)
    seen_sessions: list[Session] = []
    calls: list[tuple[list[dict[str, Any]], list[Any]]] = []

    async def fake_retrieve(
        _database: Any, _embedder: Any, session: Session, _prompt: str
    ) -> list[Any]:
        seen_sessions.append(session)
        if len(seen_sessions) == 1:
            return [SimpleNamespace(document_id=1, position=0, content="Project fact")]
        return []

    async def mock_run(
        self: Agent,
        prompt: str | None = None,
        *,
        messages: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
    ) -> Response:
        assert messages is not None
        calls.append((messages, list(self.tools)))
        return _make_response()

    inputs = iter(["question about the project", "follow-up"])

    async def fake_prompt_async(*args: Any, **kwargs: Any) -> str:
        try:
            return next(inputs)
        except StopIteration as exc:
            raise EOFError from exc

    monkeypatch.setattr("sensai.GitHubMCP", fake_github_client)
    monkeypatch.setattr("sensai.ui.app.retrieve_chunks", fake_retrieve)
    monkeypatch.setattr("sensai.ui.app.update_session", lambda *args, **kwargs: updated_session)
    monkeypatch.setattr(Agent, "run", mock_run)
    monkeypatch.setattr("sensai.ui.app.PromptSession.prompt_async", fake_prompt_async)

    main()

    assert len(calls) == 2
    assert any("Project fact" in message["content"] for message in calls[0][0])
    assert any(isinstance(tool, MCPTools) for tool in calls[0][1])
    assert seen_sessions[1] is updated_session
    assert len(clients) == 1
    assert all(client.closed and client.listed == 1 for client in clients)


def test_main_ingests_cli_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A CLI file is read and sent to the RAG ingestion path before chatting."""
    file_path = tmp_path / "notes.txt"
    file_path.write_text("A project note")
    _patch_main_dependencies(monkeypatch)
    monkeypatch.setattr("sys.argv", ["sensai", "--files", str(file_path)])
    monkeypatch.setattr("sensai.USE_MCP_MODE", False)
    monkeypatch.setattr(
        "sensai.core.setup.create_message", lambda *args, **kwargs: SimpleNamespace(id=17)
    )
    calls: list[tuple[int, bytes, str]] = []

    async def fake_ingest(
        _database: Any, _embedder: Any, message_id: int, content: bytes, name: str
    ) -> None:
        calls.append((message_id, content, name))

    async def fake_prompt_async(*args: Any, **kwargs: Any) -> str:
        raise EOFError

    monkeypatch.setattr("sensai.core.setup.ingest_document", fake_ingest)
    monkeypatch.setattr("sensai.ui.app.PromptSession.prompt_async", fake_prompt_async)

    main()

    assert calls == [(17, b"A project note", "notes.txt")]


def test_main_greets_the_profile_and_exits_on_eof(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The new CLI greets the authenticated profile and handles end of input."""
    _patch_main_dependencies(monkeypatch)
    monkeypatch.setattr("sensai.USE_MCP_MODE", False)

    async def fake_prompt_async(*args: Any, **kwargs: Any) -> str:
        raise EOFError

    monkeypatch.setattr("sensai.ui.app.PromptSession.prompt_async", fake_prompt_async)
    main()
    captured = capsys.readouterr()
    assert "Hello Default Profile! Welcome to Sensai." in captured.out
    assert "Program terminated by user." in captured.out


def test_main_closes_mcp_connection_after_cli_exit_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Slash commands remain usable and /exit closes the active MCP session."""
    _patch_main_dependencies(monkeypatch)
    monkeypatch.setattr("sensai.USE_MCP_MODE", True)
    monkeypatch.setattr("sensai.USE_GITHUB_MCP", True)
    monkeypatch.setenv("GITHUB_MCP_TOKEN", "test-token")
    client = _FakeMCPClient()
    monkeypatch.setattr("sensai.GitHubMCP", lambda: client)
    inputs = iter(["/help", "/exit"])

    async def fake_prompt_async(*args: Any, **kwargs: Any) -> str:
        assert client.connected
        return next(inputs)

    monkeypatch.setattr("sensai.ui.app.PromptSession.prompt_async", fake_prompt_async)
    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert "Available Commands" in capsys.readouterr().out
    assert client.closed
    assert not client.connected
    assert client.listed == 1
