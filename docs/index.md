# Sensai 🍜

> **Sensai** is an LLM chatbot with unlimited functionalities, designed to interact with the Ollama Sensei API and provide an enriched conversational experience.

---

## Features

- **Real-time Streaming**: Supports streaming responses for instant token output.
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

Sensai requires an API token to interact with the Sensei backend. Create a `.env` file at the root of the project:

```bash
cp .env.exemple .env
```

Set your token:

```dotenv
TOKEN="your_api_token_here"
```

### Running Sensai

Launch the command line interface:

```bash
uv run sensai
```

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
