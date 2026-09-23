"""Tests for the ``sensai.data.database.database`` module."""

import sqlite3
from pathlib import Path

import pytest

from sensai.data.database.database import Database

SCHEMA = "CREATE TABLE IF NOT EXISTS thing(id INTEGER PRIMARY KEY, name TEXT NOT NULL);"


def test_connection_is_created_lazily(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), schema=SCHEMA, name="lazy.db")

    assert not (tmp_path / "lazy.db").exists()

    _ = database.connection

    assert (tmp_path / "lazy.db").exists()
    database.close()


def test_connection_is_reused(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), schema=SCHEMA, name="reuse.db")

    assert database.connection is database.connection
    database.close()


def test_foreign_keys_pragma_is_enabled(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), schema=SCHEMA, name="fk.db")

    cursor = database.connection.execute("PRAGMA foreign_keys")

    assert cursor.fetchone()[0] == 1
    database.close()


def test_row_factory_allows_column_access_by_name(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), schema=SCHEMA, name="rows.db")
    database.initialize()

    database.execute("INSERT INTO thing (name) VALUES (?)", ("widget",))
    row = database.execute("SELECT id, name FROM thing").fetchone()

    assert row["name"] == "widget"
    database.close()


def test_initialize_executes_the_full_schema(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), schema=SCHEMA, name="init.db")

    database.initialize()

    cursor = database.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'thing'"
    )
    assert cursor.fetchone() is not None
    database.close()


def test_initialize_is_idempotent(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), schema=SCHEMA, name="idempotent.db")

    database.initialize()
    database.execute("INSERT INTO thing (name) VALUES (?)", ("widget",))
    database.initialize()

    cursor = database.execute("SELECT COUNT(*) FROM thing")
    assert cursor.fetchone()[0] == 1
    database.close()


def test_close_allows_reconnecting(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), schema=SCHEMA, name="close.db")
    database.initialize()

    database.close()
    cursor = database.execute("SELECT COUNT(*) FROM thing")

    assert cursor.fetchone()[0] == 0
    database.close()


def test_context_manager_closes_connection_on_exit(tmp_path: Path) -> None:
    with Database(path=str(tmp_path), schema=SCHEMA, name="ctx.db") as database:
        database.initialize()
        conn = database.connection

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_schema_property_returns_the_schema_text(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), schema=SCHEMA, name="schema.db")

    assert database.schema == SCHEMA
    database.close()


def test_execute_raises_on_invalid_sql(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), schema=SCHEMA, name="invalid.db")
    database.initialize()

    with pytest.raises(sqlite3.OperationalError):
        database.execute("SELECT * FROM nonexistent_table")
    database.close()
