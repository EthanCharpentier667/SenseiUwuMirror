"""Profile Manager for handling user profiles."""

from typing import TYPE_CHECKING

from peewee import SQL, CharField, DateTimeField, TextField

from sensai.data.database.base_model import BaseModel

if TYPE_CHECKING:
    from sensai.data.database.database import Database


class Profile(BaseModel):
    """A user profile, mirroring the `profile` table."""

    name = CharField()
    password = CharField()
    preferences = TextField(null=True)
    instructions = TextField(null=True)
    created_at = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])


def create_profile(
    db: "Database",
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
    with db.database.bind_ctx([Profile]):
        return Profile.create(
            name=name, password=password, preferences=preferences, instructions=instructions
        )


def get_profile(db: "Database", profile_id: int) -> Profile | None:
    """Retrieve a profile by its ID.

    Args:
        db (Database): The database to read from.
        profile_id (int): The unique identifier for the profile.

    Returns:
        Profile | None: The profile if found, otherwise None.
    """
    with db.database.bind_ctx([Profile]):
        return Profile.get_or_none(Profile.id == profile_id)


def get_profile_by_name(db: "Database", name: str) -> Profile | None:
    """Retrieve a profile by its display name.

    Args:
        db (Database): The database to read from.
        name (str): The profile's display name.

    Returns:
        Profile | None: The profile if found, otherwise None.
    """
    with db.database.bind_ctx([Profile]):
        return Profile.get_or_none(Profile.name == name)


def update_profile_preferences(db: "Database", profile_id: int, preferences: str) -> None:
    """Overwrite a profile's preferences.

    Args:
        db (Database): The database to write to.
        profile_id (int): The unique identifier for the profile.
        preferences (str): The new preferences text.
    """
    with db.database.bind_ctx([Profile]):
        Profile.update(preferences=preferences).where(Profile.id == profile_id).execute()


def update_profile_instructions(db: "Database", profile_id: int, instructions: str) -> None:
    """Overwrite a profile's instructions.

    Args:
        db (Database): The database to write to.
        profile_id (int): The unique identifier for the profile.
        instructions (str): The new instructions text.
    """
    with db.database.bind_ctx([Profile]):
        Profile.update(instructions=instructions).where(Profile.id == profile_id).execute()
