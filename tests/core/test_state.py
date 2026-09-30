"""Tests for core state."""

from pathlib import Path
from typing import Any

import pytest

from sensai.core.state import clear_credentials, get_saved_credentials, save_credentials


def test_state_management(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Patch Path.home() to use a tmp_path so we don't mess with the real home
    def fake_home(*args: Any, **kwargs: Any) -> Path:
        return tmp_path

    monkeypatch.setattr(Path, "home", fake_home)

    mock_keyring = {}

    def fake_set_pwd(service: str, username: str, password: str) -> None:
        mock_keyring[f"{service}:{username}"] = password

    def fake_get_pwd(service: str, username: str) -> str | None:
        return mock_keyring.get(f"{service}:{username}")

    def fake_del_pwd(service: str, username: str) -> None:
        mock_keyring.pop(f"{service}:{username}", None)

    monkeypatch.setattr("sensai.core.state.keyring.set_password", fake_set_pwd)
    monkeypatch.setattr("sensai.core.state.keyring.get_password", fake_get_pwd)
    monkeypatch.setattr("sensai.core.state.keyring.delete_password", fake_del_pwd)

    clear_credentials()
    user, pwd = get_saved_credentials()
    assert user is None
    assert pwd is None

    save_credentials("testuser", "testpass")
    user, pwd = get_saved_credentials()
    assert user == "testuser"
    assert pwd == "testpass"

    clear_credentials()
    user, pwd = get_saved_credentials()
    assert user is None
    assert pwd is None
