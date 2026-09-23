"""Database module for storing and retrieving chat history."""

import sqlite3
from types import TracebackType
from typing import Any, Self


class Database:
    """A SQLite database connection wrapper, lazily connected and schema-initializable."""

    def __init__(self, path: str, schema: str, name: str, timeout: float = 10.0):
        """Initialize the database with a path, schema, and name.

        Args:
            path (str): The directory path where the database file will be stored.
            schema (str): The SQL schema to initialize the database.
            name (str): The name of the database file.
            timeout (float, optional): The timeout for database operations in seconds.
                Default is 10.0 seconds.
        """
        self._path = f"{path}/{name}"
        self._schema = schema
        self._timeout = timeout
        self._conn: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        """Return the database connection, creating it if necessary.

        Returns:
            sqlite3.Connection: The database connection object.
        """
        if self._conn is None:
            self._conn = sqlite3.connect(self._path, timeout=self._timeout)
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    @property
    def schema(self) -> str:
        """Return the database schema.

        Returns:
            str: The database schema as a string.
        """
        return self._schema

    def close(self) -> None:
        """Close the database connection if it is open."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Execute a SQL query with optional parameters.

        Args:
            query (str): The SQL query to execute.
            params (tuple, optional): Parameters to substitute into the query.
                Default is an empty tuple.

        Returns:
            sqlite3.Cursor: A cursor object that can be used to fetch results from the
                executed query.
        """
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        self.connection.commit()
        return cursor

    def clear(self) -> None:
        """Clear all data from the database."""
        self.execute("DELETE FROM session")
        self.execute("DELETE FROM message")
        self.execute("DELETE FROM document")
        self.execute("DELETE FROM profile")

    def initialize(self) -> None:
        """Initialize the database with the provided schema.

        This method executes the schema SQL to set up the database structure.

        Raises:
            sqlite3.Error: If an error occurs while executing the schema SQL.
        """
        self.connection.executescript(self._schema)

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
