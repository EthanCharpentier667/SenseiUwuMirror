"""Local state management for Sensai CLI."""

import contextlib
import json
from pathlib import Path

import keyring


def _get_state_file() -> Path:
    """Get the path to the state file."""
    state_dir = Path.home() / ".sensai"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "state.json"


def get_saved_credentials() -> tuple[str | None, str | None]:
    """Load the saved credentials from the local state file and keyring.

    Returns:
        tuple[str | None, str | None]: The username and password, or (None, None).
    """
    state_file = _get_state_file()
    if not state_file.exists():
        return None, None

    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, None
    else:
        username = data.get("username")
        if not username:
            return None, None

        password = keyring.get_password("sensai_cli", username)
        return username, password


def save_credentials(username: str, password: str) -> None:
    """Save the username locally and password securely in keyring.

    Args:
        username (str): The profile's display name.
        password (str): The profile's password.
    """
    state_file = _get_state_file()
    data = {"username": username}
    state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    with contextlib.suppress(Exception):
        keyring.set_password("sensai_cli", username, password)


def clear_credentials() -> None:
    """Clear the saved credentials from the local state file and keyring."""
    username, _ = get_saved_credentials()
    if username:
        with contextlib.suppress(Exception):
            keyring.delete_password("sensai_cli", username)

    state_file = _get_state_file()
    if state_file.exists():
        with contextlib.suppress(OSError):
            state_file.unlink()
