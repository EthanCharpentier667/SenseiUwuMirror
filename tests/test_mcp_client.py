"""Tests for MCP client authentication and connection lifetime."""

from typing import Any
from unittest.mock import Mock

import httpx2
import pytest

import sensai.mcp.sensai_client as mcp_module
from sensai.mcp.sensai_client import activate_github_mcp_client, activate_mcp_client


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
    monkeypatch.setattr(mcp_module, "streamable_http_client", fake_transport)
    monkeypatch.setattr(mcp_module, "Client", fake_client)

    async with activate_github_mcp_client() as client:
        assert client is client_context.value
        assert http_context.entered
        assert client_context.entered

    assert captured == {
        "headers": {"Authorization": "Bearer test-token"},
        "url": mcp_module.GITHUB_MCP_HOST,
        "http_client": http_context,
        "transport": transport,
    }
    assert client_context.exited
    assert http_context.exited


@pytest.mark.asyncio
async def test_public_server_uses_plain_client(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeContext()
    create = Mock(return_value=fake_client)
    monkeypatch.setattr(mcp_module, "SensAIClient", create)
    url = "https://docs.mcp.cloudflare.com/mcp"

    async with activate_mcp_client(url) as client:
        assert client is fake_client.value
        assert fake_client.entered
        assert not fake_client.exited

    create.assert_called_once_with(url)
    assert fake_client.exited


@pytest.mark.asyncio
async def test_github_connection_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_MCP_TOKEN", raising=False)
    create_http_client = Mock()
    monkeypatch.setattr(httpx2, "AsyncClient", create_http_client)

    with pytest.raises(ValueError, match="GITHUB_MCP_TOKEN is required"):
        async with activate_github_mcp_client():
            pytest.fail("A connection without a token must be rejected")

    create_http_client.assert_not_called()
