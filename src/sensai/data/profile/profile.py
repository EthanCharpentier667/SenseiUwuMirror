"""Profile Manager for handling user profiles."""

from dataclasses import dataclass, field
from sqlite3 import Row

from sensai.data.database.database import Database
from sensai.data.session.session import Session


@dataclass
class Profile:
    """A user profile, mirroring the `profile` table."""

    name: str
    password: str
    preferences: str | None = None
    instructions: str | None = None
    id: int | None = None
    created_at: str | None = None
    sessions: list[Session] = field(default_factory=list)


def _row_to_profile(row: Row) -> Profile:
    return Profile(
        id=row["id"],
        password=row["password"],
        name=row["name"],
        preferences=row["preferences"],
        instructions=row["instructions"],
        created_at=row["created_at"],
        sessions=row["sessions"] if "sessions" in row.keys() else [],  # noqa: SIM118
    )


def create_profile(
    db: Database,
    name: str,
    password: str,
    preferences: str | None = None,
    instructions: str | None = None,
) -> Profile:
    """Create a new profile.

    Args:
        db (Database): The database to write to.
        name (str): The profile's display name.
        password (str): The profile's password, already hashed by the caller.
        preferences (str, optional): Free-form user preferences. Default is None.
        instructions (str, optional): Free-form custom instructions. Default is None.

    Returns:
        Profile: The newly created profile, including its assigned ID.
    """
    cursor = db.execute(
        "INSERT INTO profile (name, password, preferences, instructions) VALUES (?, ?, ?, ?)",
        (name, password, preferences, instructions),
    )
    if cursor.lastrowid is None:
        raise ValueError("Failed to create a new profile; no ID was returned.")
    profile = get_profile(db, cursor.lastrowid)
    if profile is None:
        raise ValueError(
            f"Failed to retrieve the newly created profile with ID {cursor.lastrowid}."
        )
    return profile


def get_profile(db: Database, profile_id: int) -> Profile | None:
    """Retrieve a profile by its ID.

    Args:
        db (Database): The database to read from.
        profile_id (int): The unique identifier for the profile.

    Returns:
        Profile | None: The profile if found, otherwise None.
    """
    cursor = db.execute(
        "SELECT id, name, password, preferences, instructions, created_at "
        "FROM profile WHERE id = ?",
        (profile_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_profile(row)


def _row_to_session(row: Row) -> Session:
    return Session(
        id=row["id"],
        name=row["name"],
        profile_id=row["profile_id"],
        created_at=row["created_at"],
        prompt_eval_count=row["prompt_eval_count"],
        eval_count=row["eval_count"],
        token_used=row["token_used"],
    )


def get_row_profile_sessions(db: Database, profile_id: int) -> list[Row]:
    """Retrieve all session rows associated with a profile.

    Args:
        db (Database): The database to read from.
        profile_id (int): The unique identifier for the profile.

    Returns:
        list[Row]: A list of session rows associated with the profile.
    """
    cursor = db.execute(
        "SELECT id, name, profile_id, created_at, prompt_eval_count, eval_count, token_used "
        "FROM session WHERE profile_id = ?",
        (profile_id,),
    )
    return cursor.fetchall()


def get_profile_sessions(db: Database, profile_id: int) -> list[Session]:
    """Retrieve all sessions associated with a profile.

    Args:
        db (Database): The database to read from.
        profile_id (int): The unique identifier for the profile.

    Returns:
        list[Session]: A list of sessions associated with the profile.
    """
    cursor = db.execute(
        "SELECT id, name, profile_id, created_at, prompt_eval_count, eval_count, token_used "
        "FROM session WHERE profile_id = ?",
        (profile_id,),
    )
    rows = cursor.fetchall()
    return [_row_to_session(row) for row in rows]
