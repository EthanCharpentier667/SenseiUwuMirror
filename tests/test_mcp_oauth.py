"""Tests for OAuth storage, callback handling and the SDK authorization flow."""

from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import httpx2
import pytest
from mcp.client.auth import AuthorizationCodeResult
from mcp.shared.auth import OAuthToken

from sensai.mcp.config import OAuthConfig
from sensai.mcp.oauth import OAuth, wait_for_callback
from sensai.mcp.token_storage import TokenStorage


@pytest.mark.asyncio
async def test_token_storages_are_independent() -> None:
    first, second = TokenStorage(), TokenStorage()
    tokens = OAuthToken(access_token="test-access", refresh_token="test-refresh")  # noqa: S106
    await first.set_tokens(tokens)
    assert await first.get_tokens() is tokens
    assert await second.get_tokens() is None
    assert await second.get_client_info() is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query", ["error=access_denied", "code=test", "state=test", "code=a&code=b&state=c"]
)
async def test_invalid_callbacks_report_readable_errors(monkeypatch, query):
    prompt = AsyncMock(return_value=f"http://localhost:8080/callback?{query}")
    monkeypatch.setattr("sensai.mcp.oauth.PromptSession.prompt_async", prompt)
    with pytest.raises(ValueError, match="OAuth"):
        await wait_for_callback()


@pytest.mark.asyncio
async def test_callback_preserves_state_and_issuer(monkeypatch):
    prompt = AsyncMock(
        return_value="http://localhost:8080/callback?code=c&state=s&iss=https%3A%2F%2Fauth.example"
    )
    monkeypatch.setattr("sensai.mcp.oauth.PromptSession.prompt_async", prompt)
    result = await wait_for_callback()
    assert result.code == "c"
    assert result.state == "s"
    assert result.iss == "https://auth.example"


@pytest.mark.asyncio
@pytest.mark.parametrize("expires_in", [3600, 0])
async def test_oauth_flow_obtains_and_reuses_tokens(monkeypatch, expires_in):
    """Exercise discovery, PKCE, callback and token exchange with simulated HTTP."""
    authorization = {}
    token_requests = []

    async def redirect(url):
        authorization.update(parse_qs(urlparse(url).query))

    async def callback():
        return AuthorizationCodeResult(
            code="test-code", state=authorization["state"][0], iss="https://auth.example"
        )

    monkeypatch.setattr("sensai.mcp.oauth.open_browser", redirect)
    monkeypatch.setattr("sensai.mcp.oauth.wait_for_callback", callback)
    oauth = OAuth(
        "https://example.com/mcp",
        OAuthConfig.from_dict(
            {
                "clientId": "sensai-client",
                "issuer": "https://auth.example",
                "scope": "tools:read",
            }
        ),
    )

    def respond(request):
        if request.url.host == "example.com" and request.url.path == "/mcp":
            if request.headers.get("Authorization") == "Bearer test-access":
                return httpx2.Response(200, json={"ok": True})
            return httpx2.Response(
                401,
                headers={
                    "WWW-Authenticate": 'Bearer resource_metadata="https://example.com/.well-known/oauth-protected-resource"'
                },
            )
        if request.url.path == "/.well-known/oauth-protected-resource":
            return httpx2.Response(
                200,
                json={
                    "resource": "https://example.com/mcp",
                    "authorization_servers": ["https://auth.example"],
                },
            )
        if request.url.host == "auth.example" and request.url.path.startswith("/.well-known/"):
            return httpx2.Response(
                200,
                json={
                    "issuer": "https://auth.example",
                    "authorization_endpoint": "https://auth.example/authorize",
                    "token_endpoint": "https://auth.example/token",
                    "response_types_supported": ["code"],
                    "code_challenge_methods_supported": ["S256"],
                    "token_endpoint_auth_methods_supported": ["none"],
                },
            )
        if request.url.path == "/token":
            token_requests.append(parse_qs(request.content.decode()))
            return httpx2.Response(
                200,
                json={
                    "access_token": "test-access",
                    "token_type": "Bearer",
                    "refresh_token": "test-refresh",
                    "expires_in": 3600
                    if token_requests[-1]["grant_type"] == ["refresh_token"]
                    else expires_in,
                },
            )
        pytest.fail(f"Unexpected OAuth request: {request.url}")

    async with httpx2.AsyncClient(auth=oauth, transport=httpx2.MockTransport(respond)) as client:
        assert (await client.get("https://example.com/mcp")).status_code == 200
        assert (await client.get("https://example.com/mcp")).status_code == 200
    assert len(token_requests) == (1 if expires_in else 2)
    if not expires_in:
        assert token_requests[1]["grant_type"] == ["refresh_token"]
    assert token_requests[0]["code"] == ["test-code"]
    assert "code_verifier" in token_requests[0]
    assert authorization["code_challenge_method"] == ["S256"]
    tokens = await oauth.context.storage.get_tokens()
    assert tokens is not None
    assert tokens.refresh_token == "test-refresh"  # noqa: S105
