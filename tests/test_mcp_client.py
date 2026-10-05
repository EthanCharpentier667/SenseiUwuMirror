"""Tests for MCP client connection lifetime."""

from contextlib import asynccontextmanager
from unittest.mock import Mock

import httpx2
import pytest

import sensai.mcp.sensai_client as module
from sensai.mcp.sensai_client import SensAIClient


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
async def test_json_headers_reach_transport_and_resources_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = []
    http_client = object()
    transport = object()
    active_client = object()

    @asynccontextmanager
    async def fake_http_client(*, headers):
        assert headers == {"Authorization": "Bearer test-pat"}
        events.append("open http")
        try:
            yield http_client
        finally:
            events.append("close http")

    @asynccontextmanager
    async def fake_client(value):
        assert value is transport
        events.append("open mcp")
        try:
            yield active_client
        finally:
            events.append("close mcp")

    make_transport = Mock(return_value=transport)
    monkeypatch.setattr(httpx2, "AsyncClient", fake_http_client)
    monkeypatch.setattr(module, "streamable_http_client", make_transport)
    monkeypatch.setattr(module, "Client", fake_client)
    client = SensAIClient("https://example.com/mcp")
    async with client.activate_json(headers={"Authorization": "Bearer test-pat"}) as connected:
        assert connected is active_client
        assert events == ["open http", "open mcp"]
    make_transport.assert_called_once_with("https://example.com/mcp", http_client=http_client)
    assert events == ["open http", "open mcp", "close mcp", "close http"]
