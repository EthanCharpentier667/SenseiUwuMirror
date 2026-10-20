"""Helper functions for file permissions."""

import os
from pathlib import Path


def get_file_permissions(file_path: str) -> str:
    """Get the permissions of a file in a human-readable format.

    Args:
        file_path (str): The path to the file.

    Returns:
        str: A string representing the file's permissions in octal (e.g., '754').
    """
    try:
        permissions = Path(file_path).stat().st_mode
        return oct(permissions)[-3:]
    except (OSError, ValueError):
        return "unknown"


def can_write_to_file(file_path: str) -> bool:
    """Check if the current user may write the file, creating it if it doesn't exist yet.

    An existing file must itself be writable; a new one needs a writable folder.

    Args:
        file_path (str): The path to the file.

    Returns:
        bool: True if the file is writable, False otherwise.
    """
    path = Path(file_path)
    target = path if path.exists() else path.parent
    return os.access(target, os.W_OK)


def can_read_file(file_path: str) -> bool:
    """Check if the current user may read the file.

    Args:
        file_path (str): The path to the file.

    Returns:
        bool: True if the file is readable, False otherwise.
    """
    return os.access(file_path, os.R_OK)


def can_execute_file(file_path: str) -> bool:
    """Check if the current user may execute the file.

    Args:
        file_path (str): The path to the file.

    Returns:
        bool: True if the file is executable, False otherwise.
    """
    return os.access(file_path, os.X_OK)
