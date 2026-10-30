# SensaiUwu 🍜

SensaiUwu helps a small development team check code before review, without sending it
outside the company. It runs the project's tests, observes the result, explains a
failure and, with the developer's approval, applies a fix and checks again.

**Reference scenario:** Camille Moreau, a developer at the fictional online store
Atelier Nova, checks her cart module before Malik Benali reviews it. Atelier Nova runs
Ollama on a GPU server of its own, shared by the team. See the
[full use case](docs/use-case.md).

All model calls go directly to the Ollama HTTP API, with no LLM framework.

## Team

- Ethan Charpentier
- Tom Gatin
- Eliott Raguin
- Alexis Clemot

## Setup

### 1. Install the prerequisites

- Python 3.11 to 3.13
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Ollama](https://ollama.com/download), on your machine or on your company's server

On Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -fsSL https://ollama.com/install.sh | sh
```

Some features need more: Docker for sandboxed code, Google Chrome and a display for the
browser tools, a display and a vision model for screenshots.

### 2. Download the models

Where Ollama runs:

```bash
ollama pull llama3.2:latest
ollama pull nomic-embed-text
```

`llama3.2:latest` is the default chat model and `nomic-embed-text` embeds documents for
RAG. For vision and harder tasks, also pull `qwen3.5:9b`.

### 3. Install SensaiUwu

From the repository root:

```bash
uv sync
cp .env.exemple .env
```

`.env` holds the password hashing settings for profiles, which the example file sets to
working values. Its other two values are optional:

| Variable | Needed for |
| --- | --- |
| `TOKEN` | An Ollama server that requires a bearer token. A default local Ollama doesn't |
| `API_TOKEN` | The web search and fetch tools, with a key from [your Ollama account](https://ollama.com/settings/keys) |

### 4. Launch

Make sure Ollama is running (`ollama serve` if it isn't), then:

```bash
uv run sensai --persona tester
```

The first launch asks you to create a profile. Type `/help` to list the commands.

By default, SensaiUwu uses Ollama at `http://localhost:11434/api/chat`. To use your
company's server, set the chat and embedding endpoints:

```bash
uv run sensai --persona tester \
  --url http://ollama.example.internal:11434/api/chat \
  --embed-url http://ollama.example.internal:11434/api/chat
```

## Features

| Feature | Catalog | What it does | Details |
| --- | --- | --- | --- |
| CLI chatbot | B1 | Streaming replies, session history, clean errors, selectable model | [Streaming and UI](docs/use_cases/Streaming-and-UI.md) |
| Reasoning loop | A1 | Thought, action and observation steps, validated and budgeted by the code | [ReAct](docs/use_cases/ReAct.md) |
| Human in the loop | A3 | Three trust levels; tools that change something ask for approval | [Trust levels](docs/use_cases/Tools-and-trust-levels.md) |
| MCP | T1 | Connects external MCP servers; includes a local example server | [MCP](docs/use_cases/MCP.md) |
| Sandboxed code | T2 | Runs code in a disposable Docker container | [Sandbox](docs/use_cases/Sandboxed-code.md) |
| Web search and fetch | T3 | Looks up documentation through Ollama's web API | [Web](docs/use_cases/Web-search-and-fetch.md) |
| RAG | R1 | Hybrid vector and keyword search over attached documents | [RAG](docs/use_cases/RAG.md) |
| Sessions and profiles | M1 | Saved sessions, preferences and instructions | [Sessions](docs/use_cases/Sessions.md), [Profiles](docs/use_cases/Profiles.md) |
| Personas | A5 | Role and tone from `personas.json`, switchable mid-session | [Personas](docs/use_cases/Personas.md) |
| Host tools | | Bash, files, screenshot and browser tools | [Bash](docs/use_cases/Bash.md), [Files](docs/use_cases/File-access.md), [Screenshot](docs/use_cases/Screenshot.md), [Browser](docs/use_cases/Browser.md) |
| Session compression | | Folds the history into a running summary past a token threshold | [Compression](docs/use_cases/Session-compression.md) |
| Session statistics | | Token use and context fill with `/stats` | [Statistics](docs/use_cases/Session-stats.md) |

Each sheet holds the feature's user stories, acceptance criteria and limits.

## Usage examples

**Check the cart before review.** Run this from the repository root, then ask the
question at the prompt:

```bash
uv run sensai --persona tester --files docs/demo_assets/demos/cart-spec.md
```

```text
Run the tests in docs/demo_assets/examples/demos/python-tests, tell me which behavior
fails and why, according to the attached specification.
```

SensaiUwu shows its reasoning and asks for approval before each action that isn't
read-only. Refusing a call prevents it from running. Read each proposed write before
approving it: the model can propose changing a test instead of fixing the code.

**See the exact prompt sent to the model** (system prompt, history, injected chunks and
tool results, in order):

```bash
uv run sensai --show-prompt
```

SensaiUwu warns you when a prompt reaches 90% of the context window, since Ollama drops
what doesn't fit without an error. `/stats` shows the current fill.

**Choose the model and generation parameters:**

```bash
uv run sensai --model qwen3.5:9b --num-ctx 8192 --temperature 0.2 --top-p 0.9
```

**Switch features off:**

```bash
uv run sensai --disable rag compression --disable-tool web_search web_fetch
```

**Limit what runs without approval:**

```bash
uv run sensai --trust partial
```

**Request structured final answers:**

```bash
uv run sensai --output-schema '{"type":"object","properties":{"name":{"type":"string"},"age":{"type":"integer"}},"required":["name","age"],"additionalProperties":false}'
```

The schema goes to Ollama's `format` parameter. SensaiUwu doesn't validate the reply
again or retry.

**Connect an MCP server** from the chat, as explained in the
[MCP guide](docs/mcp-server.md). To start the local example server:

```bash
uv run python src/sensai_mcp/sensai_server.py
```

`uv run sensai --help` lists every option.

## Documentation

| Page | Contents |
| --- | --- |
| [Use case](docs/use-case.md) | The scenario and the feature map |
| [Scope and decisions](docs/scope-and-decisions.md) | Why these features, and the main technical choices |
| [Limits, impact and risks](docs/responsibility.md) | Data, business impact and failure risks |
| [Benchmark](docs/benchmark.md) | Model comparison |
| [If we started over](docs/retrospective.md) | What we would change |

To browse them locally:

```bash
uv run --group docs mkdocs serve
```

## Development

| Tool | Purpose | Command |
| --- | --- | --- |
| [Ruff](https://docs.astral.sh/ruff/) | Linter | `uv run ruff check .` |
| Ruff | Formatter | `uv run ruff format .` |
| [mypy](https://mypy-lang.org/) | Static type checking (strict mode) | `uv run mypy` |
| [pytest](https://docs.pytest.org/) + coverage | Tests | `uv run pytest` |

To run the checks on every commit:

```bash
uv run pre-commit install
```
