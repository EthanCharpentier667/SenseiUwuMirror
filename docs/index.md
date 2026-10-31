# SensaiUwu 🍜

> **SensaiUwu** helps a small development team check code before review: it runs the tests, observes the result, explains a failure and, with approval, fixes it and checks again. Models run on Ollama, on hardware the company owns.

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

- **Python** 3.11 to 3.13
- **[uv](https://docs.astral.sh/uv/)** installed on your system
- **[Ollama](https://ollama.com/download)**, on your machine or on a server you own

### Installation

Clone the repository and install dependencies:

```bash
git clone git@github.com:EthanCharpentier667/SenseiUwuMirror.git
cd SenseiUwuMirror
uv sync
```

### Environment Configuration

Create a `.env` file at the root of the project, with the password hashing settings
SensaiUwu needs for profiles:

```bash
cp .env.exemple .env
```

Download the default chat and embedding models:

```bash
ollama pull llama3.2:latest
ollama pull nomic-embed-text
```

By default, SensaiUwu uses the Ollama server at `http://localhost:11434/api/chat`, with
no token. To use a company server, set `--url` to its chat endpoint and `--embed-url` to
the endpoint used for document embeddings (RAG), which doesn't follow `--url`. If that
server requires a bearer token, set `TOKEN` in `.env` or pass `--token`; `--embed-token`
does the same for embeddings. Without it, `--token` is reused only when both URLs are
the same. Keep `.env` private; it is ignored by Git.

The optional web search and fetch tools need an API key from
[your Ollama account](https://ollama.com/settings/keys), set as `API_TOKEN` in `.env`.

### Running SensaiUwu

Launch the command line interface:

```bash
uv run sensai
```

---

## Enabling and Disabling Features

Every optional feature is enabled by default and can be switched off:

| Feature       | What it does                                              |
|---------------|-----------------------------------------------------------|
| `tools`       | Let the agent call tools (built-in and MCP).              |
| `react`       | Plan tool calls with the ReAct loop before replying.      |
| `rag`         | Retrieve chunks of attached documents for each prompt.    |
| `compression` | Summarize the session history once it grows too long.     |
| `mcp`         | Connect MCP servers with `/mcp` and use their tools.      |

Disable some for one run from the command line:

```bash
uv run sensai --disable rag compression
```

Or toggle them during a conversation in `/settings` → **Features**; that choice
is saved in your profile and applied on the next launch.

Without `react` (or without any tool available), the model answers directly,
without planning, so no tool is called.

---

## MCP Connections

Connect local or remote Streamable HTTP servers from the SensaiUwu chat with
`/mcp add-json <name> '<json>'`. The [MCP connection guide](mcp-server.md)
includes step-by-step examples for the local calculator, GitHub with a token,
and GitHub with OAuth, plus configuration fields and troubleshooting.

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
