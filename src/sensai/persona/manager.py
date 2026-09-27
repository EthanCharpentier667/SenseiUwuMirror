"""Persona manager for loading and switching agent personas."""

import json
from pathlib import Path
from typing import Any

from .persona import Persona

DEFAULT_PERSONAS_PATH = "personas.json"


def _parse_persona(key: str, data: dict[str, Any]) -> Persona:
    """Parse a single persona entry from a raw dictionary.

    Args:
        key: The persona's identifier key in the config file.
        data: Raw dictionary with name, description, and system_prompt fields.

    Returns:
        A fully constructed Persona instance.

    Raises:
        ValueError: If any required field is missing.
    """
    for field in ("name", "description", "system_prompt"):
        if field not in data:
            raise ValueError(f"Persona '{key}' is missing required field '{field}'.")
    return Persona(
        name=data["name"],
        description=data["description"],
        system_prompt=data["system_prompt"],
    )


def load_personas(path: str = DEFAULT_PERSONAS_PATH) -> dict[str, Persona]:
    """Load all personas from a JSON config file.

    Args:
        path: Path to the JSON personas file. Default is ``personas.json``.

    Returns:
        A mapping of persona key to Persona instance.

    Raises:
        FileNotFoundError: If the file does not exist at the given path.
        ValueError: If a persona entry is missing a required field.
    """
    personas_path = Path(path)
    if not personas_path.exists():
        raise FileNotFoundError(f"Personas file not found: {path}")
    raw: dict[str, Any] = json.loads(personas_path.read_text(encoding="utf-8"))
    return {key: _parse_persona(key, value) for key, value in raw.items()}


def get_persona(personas: dict[str, Persona], name: str) -> Persona | None:
    """Retrieve a persona by its key.

    Args:
        personas: The loaded personas mapping.
        name: The persona key to look up.

    Returns:
        The matching Persona, or None if not found.
    """
    return personas.get(name)


def list_personas(personas: dict[str, Persona]) -> list[str]:
    """Return all available persona keys.

    Args:
        personas: The loaded personas mapping.

    Returns:
        A sorted list of persona keys.
    """
    return sorted(personas.keys())
