# Itadakimasu 🍜🍜🍜 !

---

# SenseiUwuMirror

Python project for the SenseiUwuMirror team, managed with [uv](https://docs.astral.sh/uv/).

## Team

- Ethan Charpentier
- Tom Gatin
- Eliott Raguin
- Alexis Clemot

## Installation

### Install uv

On macOS and Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Check the installation:

```bash
uv --version
```

### Install the project and its dependencies

From the repository root:

```bash
uv sync
```

This command creates the `.venv` virtual environment, installs the project, and synchronizes the dependencies defined in `pyproject.toml` and `uv.lock`.

## Run the project

```bash
uv run sensai
```

To add a Python dependency to the project:

```bash
uv add package-name
```

To add a development dependency:

```bash
uv add --dev package-name
```

## Code quality

This project enforces linting, formatting, static typing, and tests, both
locally (via [pre-commit](https://pre-commit.com/)) and in CI
([.github/workflows/ci.yml](.github/workflows/ci.yml)).

| Tool | Purpose | Command |
| --- | --- | --- |
| [Ruff](https://docs.astral.sh/ruff/) | Linter | `uv run ruff check .` |
| Ruff | Formatter | `uv run ruff format .` |
| [mypy](https://mypy-lang.org/) | Static type checking (strict mode) | `uv run mypy` |
| [pytest](https://docs.pytest.org/) + coverage | Tests | `uv run pytest` |

### One-time setup: enable pre-commit hooks

```bash
uv run pre-commit install
```

From then on, `ruff check --fix`, `ruff format`, and `mypy` run automatically
on every commit. To run all hooks on demand against the whole repo:

```bash
uv run pre-commit run --all-files
```

### Conventions

- All new code must be type-annotated; `mypy` runs in `strict` mode.
- Public modules/functions/classes use Google-style docstrings.
- Ruff is configured with `select = ["ALL"]` in `pyproject.toml`, with a
  short, documented ignore list for rules that conflict with the formatter
  or don't fit this project. When in doubt, prefer fixing the code over
  adding a new ignore.
