"""Tests for reusable MCP configuration parsing."""

import pytest

from sensai.mcp.config import MCPServerConfig


def test_http_config_without_headers() -> None:
    config = MCPServerConfig.from_json('{"type":"http","url":"https://example.com/mcp"}')

    assert config.url == "https://example.com/mcp"
    assert config.headers == {}


def test_http_config_with_headers() -> None:
    config = MCPServerConfig.from_json(
        '{"type":"http","url":"http://localhost:8000/mcp",'
        '"headers":{"Authorization":"Bearer test-token"}}'
    )

    assert config.headers == {"Authorization": "Bearer test-token"}
    assert "test-token" not in repr(config)


def test_invalid_json_reports_location() -> None:
    with pytest.raises(ValueError, match="Invalid MCP JSON at line 2, column"):
        MCPServerConfig.from_json('{\n"type":}')
