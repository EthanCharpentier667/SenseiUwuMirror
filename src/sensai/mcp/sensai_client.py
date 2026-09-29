"""Client MCP de SensAI."""

from mcp import Client


class SensAIClient(Client):
    """Client connecté au serveur MCP local."""

    def __init__(self, server_url: str) -> None:
        """Configurer l'adresse du serveur."""
        super().__init__(server_url)


def activate_mcp_client(server_url: str) -> SensAIClient:
    """Activate the MCP client for SensAI."""
    return SensAIClient(server_url)
