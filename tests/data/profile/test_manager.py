"""Tests for the ``sensai.data.profile.manager`` module."""

import re

import pytest

from sensai.data.database.database import Database
from sensai.data.profile.manager import (
    ProfileManager,
    create_new_profile,
    login,
    logout,
)


def test_create_new_profile_hashes_the_password(db: Database) -> None:
    profile = create_new_profile(db, "Ada", "secret")

    assert profile.password != "secret"  # noqa: S105
    assert ProfileManager.current_profile is profile


def test_login_succeeds_with_the_correct_password(db: Database) -> None:
    create_new_profile(db, "Ada", "secret")
    logout()

    profile = login("Ada", "secret", db)

    if profile is None:
        raise ValueError("Login failed; profile is None.")
    assert profile.name == "Ada"
    assert ProfileManager.current_profile is profile


def test_login_rejects_the_wrong_password(db: Database) -> None:
    create_new_profile(db, "Ada", "secret")
    logout()

    profile = login("Ada", "wrong", db)

    assert profile is None
    assert ProfileManager.current_profile is None


def test_login_rejects_an_unknown_profile(db: Database) -> None:
    profile = login("Nobody", "secret", db)

    assert profile is None
    assert ProfileManager.current_profile is None


@pytest.mark.parametrize("env_var", ["HASH_ALGORITHM", "HASH_ITERATIONS", "SALT_BYTES"])
def test_create_new_profile_requires_each_hash_env_var(
    db: Database, monkeypatch: pytest.MonkeyPatch, env_var: str
) -> None:
    monkeypatch.delenv(env_var, raising=False)

    with pytest.raises(ValueError, match=re.escape(f"{env_var} environment variable must be set")):
        create_new_profile(db, "Ada", "secret")


def test_login_requires_hash_algorithm(db: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    create_new_profile(db, "Ada", "secret")
    logout()

    monkeypatch.delenv("HASH_ALGORITHM", raising=False)

    with pytest.raises(ValueError, match="HASH_ALGORITHM environment variable must be set"):
        login("Ada", "secret", db)
