"""Tests for the ``sensai.data.database.database`` module."""

from pathlib import Path

from sensai.data.database.database import Database
from sensai.data.profile.profile import Profile, create_profile
from sensai.data.session.document import Document
from sensai.data.session.message import Message
from sensai.data.session.session import Session

_TABLES = {"profile", "session", "message", "document"}


def test_connection_is_created_lazily(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), name="lazy.db")

    assert not (tmp_path / "lazy.db").exists()

    database.initialize()

    assert (tmp_path / "lazy.db").exists()
    database.close()


def test_foreign_keys_pragma_is_enabled(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), name="fk.db")
    database.initialize()

    with database.database.bind_ctx([Profile]):
        cursor = database.database.execute_sql("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 1
    database.close()


def test_initialize_creates_all_tables(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), name="init.db")

    database.initialize()

    with database.database.bind_ctx([Profile]):
        cursor = database.database.execute_sql(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
        table_names = {row[0] for row in cursor.fetchall()}
    assert _TABLES.issubset(table_names)
    database.close()


def test_initialize_is_idempotent(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), name="idempotent.db")

    database.initialize()
    create_profile(database, "Ada", "secret")
    database.initialize()

    with database.database.bind_ctx([Profile]):
        assert Profile.select().count() == 1
    database.close()


def test_clear_empties_every_table(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), name="clear.db")
    database.initialize()
    create_profile(database, "Ada", "secret")

    database.clear()

    with database.database.bind_ctx([Profile, Session, Message, Document]):
        assert Profile.select().count() == 0
        assert Session.select().count() == 0
        assert Message.select().count() == 0
        assert Document.select().count() == 0
    database.close()


def test_close_allows_reconnecting(tmp_path: Path) -> None:
    database = Database(path=str(tmp_path), name="close.db")
    database.initialize()

    database.close()
    create_profile(database, "Ada", "secret")

    with database.database.bind_ctx([Profile]):
        assert Profile.select().count() == 1
    database.close()


def test_context_manager_closes_connection_on_exit(tmp_path: Path) -> None:
    with Database(path=str(tmp_path), name="ctx.db") as database:
        database.initialize()
        assert not database.database.is_closed()

    assert database.database.is_closed()
