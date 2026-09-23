"""Shared pytest fixtures for the sensai test suite."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from sensai.data.database.database import Database
from sensai.data.session.manager import SessionManager

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "src" / "sensai" / "data" / "database" / "schema.sql"
)


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    """A real SQLite database, initialized with the project's schema, in a temp directory."""
    database = Database(path=str(tmp_path), schema=SCHEMA_PATH.read_text(), name="test.db")
    database.initialize()
    yield database
    database.close()


@pytest.fixture
def profile_id(db: Database) -> int:
    """Insert a minimal profile row and return its id.

    There is no profile_manager module yet, so this inserts directly.
    """
    cursor = db.execute(
        "INSERT INTO profile (name, password) VALUES (?, ?)", ("Test Profile", "secret")
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


@pytest.fixture(autouse=True)
def _reset_current_session() -> Iterator[None]:
    """Prevent SessionManager's shared class-level state from leaking between tests."""
    SessionManager.current_session = None
    yield
    SessionManager.current_session = None
