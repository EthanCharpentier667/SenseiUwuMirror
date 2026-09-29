"""Example MCP client connecting to the local SensAI server."""

import anyio
from mcp import Client


async def main() -> None:
    """Connect to the MCP server and display its advertised capabilities."""
    async with Client("http://localhost:8000/mcp") as client:
        print(client.server_capabilities.model_dump(exclude_none=True))  # noqa: T201


if __name__ == "__main__":
    anyio.run(main)
