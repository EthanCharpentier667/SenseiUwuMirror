"""Tests for the ``sensai.core.setup`` module."""

from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from sensai.client import OllamaClient
from sensai.core import setup
from sensai.data.database.database import Database
from sensai.data.session.session import create_session
from sensai.features.features import Features
from sensai.features.rag.embedder import Embedder


async def _ingest_files(
    db: Database, profile_id: int, files: list[Path], failing_name: str | None = None
) -> tuple[str, list[str]]:
    """Ingest files at startup, failing on one name, and return the output and the ingested."""
    ingested: list[str] = []

    async def fake_ingest(*args: object) -> None:
        name = str(args[-1])
        if name == failing_name:
            msg = "No text"
            raise ValueError(msg)
        ingested.append(name)

    output = StringIO()
    session = create_session(db, profile_id)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(setup, "ingest_document", fake_ingest)
        await setup.ingest_initial_files(
            db,
            Embedder(OllamaClient("http://localhost:11434/api/chat", token=None, timeout=1.0)),
            session,
            files,
            Console(file=output, width=500),
            features=Features(),
        )
    return output.getvalue(), ingested


@pytest.mark.asyncio
async def test_ingest_initial_files_reports_success(
    db: Database, profile_id: int, tmp_path: Path
) -> None:
    file = tmp_path / "spec.md"
    file.write_text("Spec")

    output, ingested = await _ingest_files(db, profile_id, [file])

    assert ingested == ["spec.md"]
    assert "Successfully ingested" in output
    assert "Failed to ingest" not in output


@pytest.mark.asyncio
async def test_ingest_initial_files_reports_no_success_after_a_failure(
    db: Database, profile_id: int, tmp_path: Path
) -> None:
    failing = tmp_path / "scan.pdf"
    failing.write_text("Scan")
    valid = tmp_path / "spec.md"
    valid.write_text("Spec")

    output, ingested = await _ingest_files(db, profile_id, [failing, valid], "scan.pdf")

    assert ingested == ["spec.md"]
    assert f"Failed to ingest file: {failing}" in output
    assert f"Successfully ingested file: {failing}" not in output
    assert f"Successfully ingested file: {valid}" in output
