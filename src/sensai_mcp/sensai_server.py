"""Example MCP server exposing a calculator tool and a greeting resource."""

from mcp.server import MCPServer

mcp = MCPServer("Demo")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@mcp.resource("greeting://{name}")
def greeting(name: str) -> str:
    """Return a greeting message for the given name."""
    return f"Hello, {name}!"


@mcp.prompt()
def summarize_text(text: str) -> str:
    """Summarize the given text."""
    return f"Summary of the text: {text[:50]}..."


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
