"""Profile Manager for handling user profiles."""

import crypt

from sensai.data.database.database import Database

from .profile import Profile
from .profile import create_profile as _create_profile


class ProfileManager:
    """Holds the process-wide currently active profile."""

    current_profile: Profile | None = None


def get_current_profile() -> Profile | None:
    """Retrieve the current active profile.

    Returns:
        Profile | None: The current profile if set, otherwise None.
    """
    return ProfileManager.current_profile


def is_connected() -> bool:
    """Check if there is a current active profile.

    Returns:
        bool: True if there is a current profile, False otherwise.
    """
    return ProfileManager.current_profile is not None


def login(name: str, password: str, db: Database) -> Profile:
    """Set the current active profile by verifying credentials.

    Args:
        name (str): The profile's display name.
        password (str): The profile's password.
        db (Database): The database to read from.

    Returns:
        Profile: The profile that was set as current.

    Raises:
        ValueError: If the profile does not exist or the password is incorrect.
    """
    cursor = db.execute(
        "SELECT * FROM profile WHERE name = ?",
        (name,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError(f"Profile with name '{name}' does not exist.")

    stored_password = row["password"]
    if crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512)) != stored_password:
        raise ValueError("Incorrect password.")

    profile = Profile(
        id=row["id"],
        name=row["name"],
        password=stored_password,
        preferences=row["preferences"],
        instructions=row["instructions"],
        created_at=row["created_at"],
    )
    ProfileManager.current_profile = profile
    return profile


def logout() -> None:
    """Clear the current active profile."""
    ProfileManager.current_profile = None


def create_profile(db: Database, name: str, password: str) -> Profile:
    """Create a new profile and set it as the current profile.

    Args:
        db (Database): The database to write to.
        name (str): The profile's display name.
        password (str): The profile's password.

    Returns:
        Profile: The newly created profile, including its assigned ID.
    """
    hashed_password = crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
    profile = _create_profile(db, name, hashed_password)
    ProfileManager.current_profile = profile
    return profile


def add_preference(db: Database, preference: str) -> None:
    """Add a preference to the current profile.

    Args:
        db (Database): The database to write to.
        preference (str): The preference to add.

    Raises:
        ValueError: If there is no current profile.
    """
    if ProfileManager.current_profile is None:
        raise ValueError("No current profile set.")

    current_preferences = ProfileManager.current_profile.preferences or ""
    updated_preferences = f"{current_preferences}\n{preference}".strip()

    db.execute(
        "UPDATE profile SET preferences = ? WHERE id = ?",
        (updated_preferences, ProfileManager.current_profile.id),
    )

    ProfileManager.current_profile.preferences = updated_preferences


def add_instruction(db: Database, instruction: str) -> None:
    """Add an instruction to the current profile.

    Args:
        db (Database): The database to write to.
        instruction (str): The instruction to add.

    Raises:
        ValueError: If there is no current profile.
    """
    if ProfileManager.current_profile is None:
        raise ValueError("No current profile set.")

    current_instructions = ProfileManager.current_profile.instructions or ""
    updated_instructions = f"{current_instructions}\n{instruction}".strip()

    db.execute(
        "UPDATE profile SET instructions = ? WHERE id = ?",
        (updated_instructions, ProfileManager.current_profile.id),
    )

    ProfileManager.current_profile.instructions = updated_instructions
