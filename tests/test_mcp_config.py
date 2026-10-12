"""Tests for reusable MCP configuration parsing."""

import json

import pytest

from sensai.mcp.mcp_server_config import MCPServerConfig


def test_http_config_without_headers() -> None:
    config = MCPServerConfig.from_json('{"url":"https://example.com/mcp"}')

    assert config.url == "https://example.com/mcp"
    assert config.headers == {}


def test_http_config_with_headers() -> None:
    config = MCPServerConfig.from_json(
        '{"url":"http://localhost:8000/mcp","headers":{"Authorization":"Bearer test-token"}}'
    )

    assert config.headers == {"Authorization": "Bearer test-token"}
    assert "test-token" not in repr(config)


def test_invalid_json_reports_location() -> None:
    with pytest.raises(ValueError, match="Invalid MCP JSON at line 2, column"):
        MCPServerConfig.from_json('{\n"url":}')


def test_oauth_configuration_is_optional() -> None:
    config = MCPServerConfig.from_json(
        '{"url":"https://example.com/mcp","oauth":{"scope":"tools:read","redirectUri":"http://localhost:3030/callback"}}'
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
        {"redirectUri": "http://localhost:8080/callback", "scope": 42},
        {"redirectUri": "http://localhost:8080/callback", "clientSecret": "secret"},
        {"redirectUri": "http://localhost:8080/callback", "clientId": "id"},
        {"redirectUri": "invalid"},
    ],
)
def test_invalid_oauth_options_are_rejected(oauth):
    with pytest.raises((ValueError, TypeError)):
        MCPServerConfig.from_json(json.dumps({"url": "https://example.com/mcp", "oauth": oauth}))


def test_oauth_and_static_authorization_cannot_be_combined() -> None:
    with pytest.raises(ValueError, match="Choose OAuth"):
        MCPServerConfig.from_json(
            '{"url":"https://example.com/mcp",'
            '"headers":{"authorization":"Bearer token"},'
            '"oauth":{"redirectUri":"http://localhost:8080/callback"}}'
        )


@pytest.mark.parametrize("oauth", [{}, {"scope": "tools:read"}])
def test_oauth_requires_explicit_callback(oauth):
    with pytest.raises(ValueError, match="redirectUri"):
        MCPServerConfig.from_json(json.dumps({"url": "https://example.com/mcp", "oauth": oauth}))


@pytest.mark.parametrize(
    "callback",
    ["http://127.0.0.1:9000/custom-callback", "https://agent.example.net/oauth/return"],
)
def test_oauth_preserves_personalized_callback(callback):
    config = MCPServerConfig.from_json(
        json.dumps(
            {
                "url": "https://example.com/mcp",
                "oauth": {"redirectUri": callback},
            }
        )
    )
    assert config.oauth is not None
    assert config.oauth.metadata.redirect_uris is not None
    assert str(config.oauth.metadata.redirect_uris[0]) == callback
