# Local MCP server

Sensai includes an example MCP server at `src/sensai_mcp/sensai_server.py`. It exposes:

- `add(a, b)`: a callable calculator tool that returns the sum of two integers.
- `greeting://{name}`: a resource that returns a greeting.
- `summarize_text(text)`: a prompt template.

The tool, resource and prompt are different MCP capabilities. The agent discovers callable tools through `list_tools()`; the resource and prompt are available through their own MCP methods.

## Start the server

From the repository root, install the dependencies and start the server:

```bash
uv sync
uv run python src/sensai_mcp/sensai_server.py
```

Keep this terminal open. The server listens on `http://127.0.0.1:8000/mcp` using Streamable HTTP.

## Check the connection

In a second terminal, run:

```bash
uv run python - <<'PY'
import anyio
from mcp import Client

async def main() -> None:
    async with Client("http://127.0.0.1:8000/mcp") as client:
        tools = await client.list_tools()
        print([tool.name for tool in tools.tools])
        result = await client.call_tool("add", {"a": 2, "b": 3})
        print(result.is_error, [getattr(block, "text", None) for block in result.content])

anyio.run(main)
PY
```

The output should include `['add']` and `False ['5']`. `False` means the tool call did not report an error.

## Use it with Sensai

Start `uv run sensai`, then connect from the chat prompt:

```text
/mcp http://127.0.0.1:8000/mcp
```

To connect using an HTTP JSON configuration, including optional headers, enter:

```text
/mcp add-json github '{"type":"http","url":"https://api.githubcopilot.com/mcp","headers":{"Authorization":"Bearer YOUR_GITHUB_PAT"}}'
```

Replace `YOUR_GITHUB_PAT` with your token. Enclose the JSON in single quotes to
preserve its double quotes and spaces. Write `https://` without a backslash.
Only `"type": "http"` is supported. `headers` is optional and must contain string
values. The connection name must be unique in the current session. Configurations
are used for the current conversation and are not saved for the next launch.

Sensai starts with local tools only. The `/mcp <url>` command adds remote tools to the current
agent without resetting the conversation. Connections stay open until you exit the
CLI. Repeating a connection does not add duplicate tools. Several servers can be
connected if their tool names do not conflict. `/help` lists the available commands.

If port 8000 is already occupied, check the process using it before starting another server:

```bash
ss -ltnp 'sport = :8000'
```

MkDocs also uses port 8000 by default. To preview the documentation while the MCP server is running, start MkDocs on another port:

```bash
uv run --group docs mkdocs serve -a 127.0.0.1:8001
```

See the [MCP Python client documentation](https://py.sdk.modelcontextprotocol.io/client/) for more about `list_tools()`, `call_tool()` and connection lifetime.
