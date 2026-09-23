"""Profile Manager for handling user profiles."""

from dataclasses import dataclass
from sqlite3 import Row

from .database.database import Database


@dataclass
class Profile:
    """A user profile, mirroring the `profile` table."""

    name: str
    preferences: str | None = None
    instructions: str | None = None
    id: int | None = None
    created_at: str | None = None


def _row_to_profile(row: Row) -> Profile:
    return Profile(
        id=row["id"],
        name=row["name"],
        preferences=row["preferences"],
        instructions=row["instructions"],
        created_at=row["created_at"],
    )


def create_profile(
    db: Database, name: str, preferences: str | None = None, instructions: str | None = None
) -> Profile:
    """Create a new profile.

    Args:
        db (Database): The database to write to.
        name (str): The profile's display name.
        preferences (str, optional): Free-form user preferences. Default is None.
        instructions (str, optional): Free-form custom instructions. Default is None.

    Returns:
        Profile: The newly created profile, including its assigned ID.
    """
    cursor = db.execute(
        "INSERT INTO profile (name, preferences, instructions) VALUES (?, ?, ?)",
        (name, preferences, instructions),
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
        "SELECT id, name, preferences, instructions, created_at FROM profile WHERE id = ?",
        (profile_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_profile(row)
