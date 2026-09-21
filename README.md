# Itadakimasu !

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
uv run sensei-uwu-mirror
```

To add a Python dependency to the project:

```bash
uv add package-name
```

To add a development dependency:

```bash
uv add --dev package-name
```
