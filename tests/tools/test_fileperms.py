"""Tests for the ``sensai.features.tools.fileaccess.fileperms`` module."""

from pathlib import Path

from sensai.features.tools.fileaccess.fileperms import can_read_file, can_write_to_file


def test_a_new_file_is_writable_in_a_writable_folder(tmp_path: Path) -> None:
    assert can_write_to_file(str(tmp_path / "new.md"))


def test_a_read_only_file_is_not_writable(tmp_path: Path) -> None:
    path = tmp_path / "locked.md"
    path.write_text("x", encoding="utf-8")
    path.chmod(0o444)

    assert not can_write_to_file(str(path))
    assert can_read_file(str(path))


def test_a_file_in_a_missing_folder_is_not_writable(tmp_path: Path) -> None:
    assert not can_write_to_file(str(tmp_path / "missing" / "new.md"))


def test_a_missing_file_is_not_readable(tmp_path: Path) -> None:
    assert not can_read_file(str(tmp_path / "missing.md"))
