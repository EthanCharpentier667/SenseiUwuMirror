"""Tests for reusable MCP configuration parsing."""

import json

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


def test_oauth_configuration_is_optional() -> None:
    config = MCPServerConfig.from_json(
        '{"type":"http","url":"https://example.com/mcp","oauth":{"scope":"tools:read","redirectUri":"http://localhost:3030/callback"}}'
    )
    assert config.oauth is not None
    assert config.oauth.metadata.scope == "tools:read"
    assert config.oauth.metadata.redirect_uris is not None
    assert str(config.oauth.metadata.redirect_uris[0]) == "http://localhost:3030/callback"


@pytest.mark.parametrize(
    "oauth",
    [
        None,
        True,
        {"scope": 42},
        {"clientSecret": "secret"},
        {"clientId": "id"},
        {"redirectUri": "invalid"},
    ],
)
def test_invalid_oauth_options_are_rejected(oauth):
    with pytest.raises((ValueError, TypeError)):
        MCPServerConfig.from_json(
            json.dumps({"type": "http", "url": "https://example.com/mcp", "oauth": oauth})
        )


def test_oauth_and_static_authorization_cannot_be_combined() -> None:
    with pytest.raises(ValueError, match="Choose OAuth"):
        MCPServerConfig.from_json(
            '{"type":"http","url":"https://example.com/mcp",'
            '"headers":{"authorization":"Bearer token"},"oauth":{}}'
        )
