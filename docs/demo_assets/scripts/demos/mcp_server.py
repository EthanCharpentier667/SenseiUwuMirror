"""Local, read-only MCP fixture used to record the Sensai feature sheets."""

from mcp.server.mcpserver import MCPServer

server = MCPServer("Atelier Nova demo", log_level="ERROR")


@server.tool()
def cart_rule(rule_id: str) -> str:
    """Read a fictional cart acceptance rule without contacting an external service."""
    if rule_id == "CART-EMPTY-001":
        return "CART-EMPTY-001: An empty cart has subtotal 0."
    return "Unknown cart rule. No result is available for this identifier."


if __name__ == "__main__":
    server.run(transport="streamable-http", host="127.0.0.1", port=18876)
