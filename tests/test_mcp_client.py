"""Tests for MCP client authentication and connection lifetime."""

from typing import Any
from unittest.mock import Mock

import httpx2
import pytest

import sensai.mcp.github_mcp as github_module
from sensai.mcp.github_mcp import GITHUB_MCP_HOST, GitHubMCP
from sensai.mcp.sensai_client import SensAIClient


class FakeContext:
    """Record entry and exit of an asynchronous resource."""

    def __init__(self, value: Any = None) -> None:
        """Store the optional value returned on entry."""
        self.value = value if value is not None else self
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> Any:
        """Record entry and provide the configured value."""
        self.entered = True
        return self.value

    async def __aexit__(self, *_args: object) -> None:
        """Record exit."""
        self.exited = True


@pytest.mark.asyncio
async def test_github_token_reaches_http_transport_only_during_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    http_context = FakeContext()
    client_context = FakeContext(value=object())
    transport = object()

    def fake_http_client(*, headers: dict[str, str]) -> FakeContext:
        captured["headers"] = headers
        return http_context

    def fake_transport(url: str, *, http_client: Any) -> object:
        captured["url"] = url
        captured["http_client"] = http_client
        return transport

    def fake_client(value: object) -> FakeContext:
        captured["transport"] = value
        return client_context

    monkeypatch.setenv("GITHUB_MCP_TOKEN", "test-token")
    monkeypatch.setattr(httpx2, "AsyncClient", fake_http_client)
    monkeypatch.setattr(github_module, "streamable_http_client", fake_transport)
    monkeypatch.setattr(github_module, "Client", fake_client)

    async with GitHubMCP().activate() as client:
        assert client is client_context.value
        assert http_context.entered
        assert client_context.entered

    assert captured == {
        "headers": {"Authorization": "Bearer test-token"},
        "url": GITHUB_MCP_HOST,
        "http_client": http_context,
        "transport": transport,
    }
    assert client_context.exited
    assert http_context.exited


@pytest.mark.asyncio
async def test_public_server_uses_plain_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """The public client yields itself and closes its connection on exit."""
    entered = False
    exited = False

    async def fake_enter(self: SensAIClient) -> SensAIClient:
        nonlocal entered
        entered = True
        return self

    async def fake_exit(self: SensAIClient, *_args: object) -> None:
        nonlocal exited
        exited = True

    monkeypatch.setattr(SensAIClient, "__aenter__", fake_enter)
    monkeypatch.setattr(SensAIClient, "__aexit__", fake_exit)
    client = SensAIClient("https://docs.mcp.cloudflare.com/mcp")

    async with client.activate() as active_client:
        assert active_client is client
        assert entered
        assert not exited

    assert exited


@pytest.mark.asyncio
async def test_github_connection_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_MCP_TOKEN", raising=False)
    create_http_client = Mock()
    monkeypatch.setattr(httpx2, "AsyncClient", create_http_client)

    with pytest.raises(ValueError, match="GITHUB_MCP_TOKEN is required"):
        async with GitHubMCP().activate():
            pytest.fail("A connection without a token must be rejected")

    create_http_client.assert_not_called()
