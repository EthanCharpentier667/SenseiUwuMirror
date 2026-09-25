"""Profile Manager for handling user profiles."""

import hashlib
import hmac
import os

from sensai.data.database.database import Database

from .profile import (
    Profile,
    create_profile,
    get_profile_by_name,
    update_profile_instructions,
    update_profile_preferences,
)


def _required_env(name: str) -> str:
    """Read a required environment variable.

    Args:
        name (str): The environment variable's name.

    Returns:
        str: Its value.

    Raises:
        ValueError: If the variable is not set (or empty). These are security-critical
            password-hashing parameters, so they must never silently fall back to an
            implicit default.
    """
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} environment variable must be set for password hashing.")
    return value


def _hash_password(password: str) -> str:
    """Hash a password for storage, embedding a fresh random salt.

    Args:
        password (str): The plaintext password to hash.

    Returns:
        str: The hash, formatted as ``iterations$salt_hex$digest_hex``.

    Raises:
        ValueError: If ``HASH_ALGORITHM``, ``HASH_ITERATIONS`` or ``SALT_BYTES`` is not
            set in the environment.
    """
    algorithm = _required_env("HASH_ALGORITHM")
    iterations = int(_required_env("HASH_ITERATIONS"))
    salt_bytes = int(_required_env("SALT_BYTES"))
    salt = os.urandom(salt_bytes)
    digest = hashlib.pbkdf2_hmac(algorithm, password.encode(), salt, iterations)
    return f"{iterations}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Check a plaintext password against a hash produced by ``_hash_password``.

    Args:
        password (str): The plaintext password to check.
        stored_hash (str): The stored ``iterations$salt_hex$digest_hex`` hash.

    Returns:
        bool: True if the password matches, otherwise False.

    Raises:
        ValueError: If ``HASH_ALGORITHM`` is not set in the environment.
    """
    algorithm = _required_env("HASH_ALGORITHM")
    iterations, salt_hex, digest_hex = stored_hash.split("$")
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac(algorithm, password.encode(), salt, int(iterations))
    return hmac.compare_digest(digest.hex(), digest_hex)


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


def login(name: str, password: str, db: Database) -> Profile | None:
    """Set the current active profile by verifying credentials.

    Args:
        name (str): The profile's display name.
        password (str): The profile's password.
        db (Database): The database to read from.

    Returns:
        Profile: The profile that was set as current, or None if login failed.
    """
    profile = get_profile_by_name(db, name)
    if profile is None:
        return None

    if not _verify_password(password, profile.password):
        return None

    ProfileManager.current_profile = profile
    return profile


def logout() -> None:
    """Clear the current active profile."""
    ProfileManager.current_profile = None


def create_new_profile(db: Database, name: str, password: str) -> Profile:
    """Create a new profile and set it as the current profile.

    Args:
        db (Database): The database to write to.
        name (str): The profile's display name.
        password (str): The profile's password.

    Returns:
        Profile: The newly created profile, including its assigned ID.
    """
    hashed_password = _hash_password(password)
    profile = create_profile(db, name, hashed_password)
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
    current_profile_id = ProfileManager.current_profile.id
    if current_profile_id is None:
        raise ValueError("Current profile does not have a valid ID.")

    current_preferences = ProfileManager.current_profile.preferences or ""
    updated_preferences = f"{current_preferences}\n{preference}".strip()

    update_profile_preferences(db, current_profile_id, updated_preferences)

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
    current_profile_id = ProfileManager.current_profile.id
    if current_profile_id is None:
        raise ValueError("Current profile does not have a valid ID.")

    current_instructions = ProfileManager.current_profile.instructions or ""
    updated_instructions = f"{current_instructions}\n{instruction}".strip()

    update_profile_instructions(db, current_profile_id, updated_instructions)

    ProfileManager.current_profile.instructions = updated_instructions
