"""Tests for the ``sensai.features.tools.fileaccess.fileread`` module."""

from pathlib import Path

from sensai.features.tools.fileaccess.fileread import FileRead


def test_file_read_returns_the_content_and_asks_to_ingest_the_file(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("Des notes.", encoding="utf-8")

    result = FileRead().execute(file_path=str(path))

    assert result == {"file_path": str(path), "content": "Des notes.", "document": str(path)}


def test_file_read_reports_an_unreadable_file_without_ingesting_it(tmp_path: Path) -> None:
    path = tmp_path / "missing.md"

    result = FileRead().execute(file_path=str(path))

    assert set(result) == {"file_path", "error"}


def test_file_read_rejects_a_path_that_is_not_a_string() -> None:
    result = FileRead().execute(file_path=3)

    assert result == {"file_path": 3, "error": "Invalid file path. Must be a string."}
