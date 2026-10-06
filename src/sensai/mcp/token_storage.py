"""In-memory storage implementing the MCP SDK's asynchronous token interface."""

from mcp.shared.auth import OAuthClientInformationFull, OAuthToken


class TokenStorage:
    """Keep tokens and client information for one OAuth connection."""

    def __init__(self, client_info: OAuthClientInformationFull | None = None) -> None:
        """Initialize empty tokens and optional preregistered client credentials."""
        self._tokens: OAuthToken | None = None
        self._client_info = client_info

    async def get_tokens(self) -> OAuthToken | None:
        """Retrieve the stored tokens."""
        return self._tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Store tokens including refresh token and expiry information."""
        self._tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Retrieve the stored client information."""
        return self._client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Store registered client information."""
        self._client_info = client_info
