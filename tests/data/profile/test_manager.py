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

    assert profile.name == "Ada"
    assert ProfileManager.current_profile is profile


def test_login_rejects_the_wrong_password(db: Database) -> None:
    create_new_profile(db, "Ada", "secret")
    logout()

    with pytest.raises(ValueError, match=re.escape("Incorrect password.")):
        login("Ada", "wrong", db)


def test_login_rejects_an_unknown_profile(db: Database) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        login("Nobody", "secret", db)
