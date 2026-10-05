# Sensai 🍜

> **Sensai** is an LLM chatbot with unlimited functionalities, designed to interact with the Ollama Sensei API and provide an enriched conversational experience.

---

## Features

- **Real-time Streaming**: Supports streaming responses for instant token output.
- **Event-Driven Architecture**: Decoupled UI presentation via an async event manager (see [Event System & UI](events.md)).
- **Tools Support**: Extensible via custom tool schemas and function calling.
- **Modern uv Workflow**: Fast, deterministic package management and virtual environment handling.
- **Strict Code Quality**: Ruff for formatting & linting, strict Mypy typing, and Pytest coverage suite.

---

## Quickstart

### Prerequisites

- **Python** 3.11
- **[uv](https://docs.astral.sh/uv/)** installed on your system

### Installation

Clone the repository and install dependencies:

```bash
git clone git@github.com:EthanCharpentier667/SenseiUwuMirror.git
cd SenseiUwuMirror
uv sync
```

### Environment Configuration

The default Ollama URL points to the team's hosted Sensei backend. Ask a
maintainer of that backend for its bearer token; this is a project credential,
not a token generated in your Ollama account. Create a `.env` file at the root
of the project:

```bash
cp .env.exemple .env
```

Replace the `TOKEN` placeholder with the token you received:

```dotenv
TOKEN="your_api_token_here"
```

Keep `.env` private; it is ignored by Git. If you use a different Ollama server,
set `--url` to its chat endpoint and use the token required by that server.
The `--token` CLI option can also supply the bearer token instead of `TOKEN`.
For the optional Ollama web search and fetch tools, create an API key in
[your Ollama account](https://ollama.com/settings/keys) and set it as
`API_TOKEN` in `.env`. This key is separate from the hosted Sensei backend
`TOKEN`.

### Running Sensai

Launch the command line interface:

```bash
uv run sensai
```

---

## Local MCP Server

The example server exposes an `add` tool over MCP. See the
[MCP server guide](mcp-server.md) to start it and test the connection.

---

## Development & Quality Checks

Run the automated test suite with coverage:

```bash
uv run pytest
```

Run linter and formatter checks:

```bash
uv run ruff check .
uv run ruff format --check .
```

Run static type checking in strict mode:

```bash
uv run mypy
```

---

## Documentation

To serve the documentation locally with live-reload:

```bash
uv run --group docs mkdocs serve
```

To build static HTML assets:

```bash
uv run --group docs mkdocs build
```

---

## Team

- Ethan Charpentier
- Tom Gatin
- Eliott Raguin
- Alexis Clemot
