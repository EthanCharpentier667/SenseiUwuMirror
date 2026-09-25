"""Base peewee model shared by the project's tables, bound to a database per call."""

from peewee import AutoField, Model


class BaseModel(Model):
    """A peewee model with no database bound at class-definition time.

    Each read/write binds the concrete tables it needs to a specific ``Database`` via
    ``bind_ctx``, so the same model classes can be reused across independent SQLite files
    (e.g. one per test) instead of being locked to a single global connection.
    """

    id: int | None = AutoField()  # type: ignore[assignment]
