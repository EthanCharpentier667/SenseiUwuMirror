"""Tests for the ``sensai.data.profile_manager`` module."""

from sensai.data.database.database import Database
from sensai.data.profile_manager import create_profile, get_profile


def test_create_profile_assigns_an_id(db: Database) -> None:
    profile = create_profile(db, "Ada")

    assert profile.id is not None
    assert profile.name == "Ada"


def test_create_profile_defaults_preferences_and_instructions_to_none(db: Database) -> None:
    profile = create_profile(db, "Ada")

    assert profile.preferences is None
    assert profile.instructions is None


def test_create_profile_stores_preferences_and_instructions(db: Database) -> None:
    profile = create_profile(db, "Ada", preferences="dark mode", instructions="be concise")

    assert profile.preferences == "dark mode"
    assert profile.instructions == "be concise"


def test_get_profile_returns_none_when_missing(db: Database) -> None:
    assert get_profile(db, 9999) is None


def test_get_profile_round_trips_a_created_profile(db: Database) -> None:
    created = create_profile(db, "Ada", preferences="dark mode", instructions="be concise")
    assert created.id is not None

    fetched = get_profile(db, created.id)

    assert fetched is not None
    assert fetched.name == "Ada"
    assert fetched.preferences == "dark mode"
    assert fetched.instructions == "be concise"
