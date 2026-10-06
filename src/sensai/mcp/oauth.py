"""OAuth provider and asynchronous user interaction for MCP connections."""

import asyncio
import webbrowser
from urllib.parse import parse_qs, urlparse

from mcp.client.auth import AuthorizationCodeResult, OAuthClientProvider
from prompt_toolkit import PromptSession

from sensai.mcp.config import OAuthConfig
from sensai.mcp.token_storage import TokenStorage


async def open_browser(authorization_url: str) -> None:
    """Open the authorization page without blocking the event loop."""
    if not await asyncio.to_thread(webbrowser.open, authorization_url):
        raise RuntimeError("Could not open the browser for OAuth authorization.")


async def wait_for_callback() -> AuthorizationCodeResult:
    """Read a pasted redirect URL and handle unsuccessful authorization."""
    session = PromptSession[str]()
    try:
        redirect_url = await session.prompt_async("Paste the URL you were redirected to: ")
    except (EOFError, KeyboardInterrupt):
        raise ValueError("OAuth authorization cancelled.") from None
    params = parse_qs(urlparse(redirect_url.strip()).query)
    if "error" in params:
        raise ValueError("OAuth authorization was refused or failed. Try authenticating again.")
    if any(len(params.get(key, [])) != 1 for key in ("code", "state")):
        raise ValueError("The OAuth callback URL must contain one code and one state.")
    if len(params.get("iss", [])) > 1:
        raise ValueError("The OAuth callback URL must contain at most one issuer.")
    return AuthorizationCodeResult(
        code=params["code"][0],
        state=params["state"][0],
        iss=params.get("iss", [None])[0],
    )


class OAuth(OAuthClientProvider):
    """Configure the SDK provider using per-server JSON settings."""

    def __init__(self, server_url: str, config: OAuthConfig) -> None:
        """Initialize SDK state, token storage and asynchronous handlers."""
        super().__init__(
            server_url=server_url,
            client_metadata=config.metadata,
            storage=TokenStorage(config.client_info),
            redirect_handler=open_browser,
            callback_handler=wait_for_callback,
        )
