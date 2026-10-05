"""Tests for MCP client connection lifetime."""

from contextlib import asynccontextmanager
from unittest.mock import Mock

import httpx2
import pytest

import sensai.mcp.sensai_client as module
from sensai.mcp.config import MCPServerConfig
from sensai.mcp.sensai_client import SensAIClient


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer test-pat"}])
async def test_json_headers_reach_transport_and_resources_close(
    monkeypatch: pytest.MonkeyPatch,
    headers: dict[str, str],
) -> None:
    events = []
    expected_headers = headers
    http_client = object()
    transport = object()
    active_client = object()

    @asynccontextmanager
    async def fake_http_client(*, headers):
        assert headers == expected_headers
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
    client = SensAIClient(MCPServerConfig(url="https://example.com/mcp", headers=headers))
    async with client.activate() as connected:
        assert connected is active_client
        assert events == ["open http", "open mcp"]
    make_transport.assert_called_once_with("https://example.com/mcp", http_client=http_client)
    assert events == ["open http", "open mcp", "close mcp", "close http"]
