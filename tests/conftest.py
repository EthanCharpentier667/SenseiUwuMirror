"""Shared pytest fixtures for the sensai test suite."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from sensai.data.database.database import Database
from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import create_profile
from sensai.data.session.manager import SessionManager


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    """A real SQLite database, initialized with the project's schema, in a temp directory."""
    database = Database(path=str(tmp_path), name="test.db")
    database.initialize()
    yield database
    database.close()


@pytest.fixture
def profile_id(db: Database) -> int:
    """Insert a minimal profile row and return its id."""
    profile = create_profile(db, "Test Profile", "secret")
    assert profile.id is not None
    return profile.id


@pytest.fixture(autouse=True)
def _reset_current_session() -> Iterator[None]:
    """Prevent SessionManager's shared class-level state from leaking between tests."""
    SessionManager.current_session = None
    yield
    SessionManager.current_session = None


@pytest.fixture(autouse=True)
def _reset_current_profile() -> Iterator[None]:
    """Prevent ProfileManager's shared class-level state from leaking between tests."""
    ProfileManager.current_profile = None
    yield
    ProfileManager.current_profile = None
