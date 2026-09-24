"""Database module for storing and retrieving chat history."""

from types import TracebackType
from typing import Self

from peewee import Model, SqliteDatabase

from sensai.data.profile.profile import Profile
from sensai.data.session.document import Document
from sensai.data.session.message import Message
from sensai.data.session.session import Session

_MODELS: list[type[Model]] = [Profile, Session, Message, Document]


class Database:
    """A SQLite database connection wrapper, backed by peewee, lazily connected."""

    def __init__(self, path: str, name: str, timeout: float = 10.0):
        """Initialize the database with a path and a name.

        Args:
            path (str): The directory path where the database file will be stored.
            name (str): The name of the database file.
            timeout (float, optional): The timeout for database operations in seconds.
                Default is 10.0 seconds.
        """
        self._db = SqliteDatabase(
            f"{path}/{name}",
            pragmas={"foreign_keys": 1},
            timeout=timeout,
        )

    @property
    def database(self) -> SqliteDatabase:
        """Return the underlying peewee database, connecting it if necessary.

        Returns:
            SqliteDatabase: The peewee database object models bind to for a query.
        """
        return self._db

    def close(self) -> None:
        """Close the database connection if it is open."""
        if not self._db.is_closed():
            self._db.close()

    def initialize(self) -> None:
        """Create the project's tables if they don't already exist."""
        with self._db.bind_ctx(_MODELS):
            self._db.create_tables(_MODELS)

    def clear(self) -> None:
        """Delete all rows from the project's tables, children before parents."""
        with self._db.bind_ctx(_MODELS):
            for model in reversed(_MODELS):
                model.delete().execute()

    def __enter__(self) -> Self:
        """Enter the runtime context related to this object.

        Returns:
            Self: The database instance itself.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the runtime context related to this object.

        This method is called when exiting the context of a `with` statement.

        Args:
            exc_type: The exception type, if an exception occurred.
            exc_val: The exception value, if an exception occurred.
            exc_tb: The traceback object, if an exception occurred.
        """
        self.close()
