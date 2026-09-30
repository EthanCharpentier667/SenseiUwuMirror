"""Tests for the ``sensai`` package entry point."""

from types import SimpleNamespace
from typing import Any, Self

import pytest
from mcp.types import Tool as MCPToolDefinition

from sensai import Agent, main
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


async def _fake_maybe_compress_session(*_args: Any, **_kwargs: Any) -> Session:
    return _make_session()


def _patch_main_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["sensai"])
    monkeypatch.setattr("sensai.Database", _FakeDatabase)
    monkeypatch.setattr("sensai.login", lambda *args, **kwargs: None)
    monkeypatch.setattr("sensai.create_new_profile", _make_profile)
    monkeypatch.setattr("sensai.add_preference", lambda *args, **kwargs: None)
    monkeypatch.setattr("sensai.add_instruction", lambda *args, **kwargs: None)
    monkeypatch.setattr("sensai.create_new_session", lambda *args, **kwargs: _make_session())
    monkeypatch.setattr("sensai.update_session", lambda *args, **kwargs: _make_session())
    monkeypatch.setattr("sensai.maybe_compress_session", _fake_maybe_compress_session)


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

    def fake_input(_prompt: str) -> str:
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
    monkeypatch.setattr("sensai.activate_github_mcp_client", fake_github_client)
    monkeypatch.setattr("sensai.activate_mcp_client", fake_public_client)
    monkeypatch.setattr(Agent, "run", mock_run)
    monkeypatch.setattr("builtins.input", fake_input)

    main()

    assert routes == ([expected_route] * 2 if expected_route else [])
    assert len(clients) == (2 if expected_route else 0)
    assert all(client.closed and not client.connected and client.listed == 1 for client in clients)
    _assert_agent_calls(calls, expected_route)
