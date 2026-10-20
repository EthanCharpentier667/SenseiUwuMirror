"""Tests for the ``sensai.features.tools.bash`` module."""

import asyncio
import os
from pathlib import Path

import pytest

from sensai.features.tools import bash
from sensai.features.tools.bash import BashJobTool, BashTool


@pytest.mark.asyncio
async def test_bash_runs_a_command_in_the_foreground() -> None:
    result = await BashTool().execute(command="echo hi; exit 3")

    assert result == {"command": "echo hi; exit 3", "exit_code": 3, "output": "hi\n"}


@pytest.mark.asyncio
async def test_bash_stops_a_foreground_command_that_runs_too_long(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bash, "TIMEOUT_SECONDS", 0.1)

    result = await BashTool().execute(command="sleep 5")

    assert "Timed out" in result["error"]
    assert "background" in result["error"]


@pytest.mark.asyncio
async def test_bash_rejects_an_empty_command() -> None:
    assert await BashTool().execute(command="  ") == {
        "error": "Invalid command. Must be a non-empty string."
    }


@pytest.mark.asyncio
async def test_a_background_job_runs_while_other_work_goes_on() -> None:
    started = await BashTool().execute(command="sleep 0.3; echo built", background=True)

    assert started["status"] == "running"
    running = await BashJobTool().execute(job_id=started["job_id"])
    assert running["status"] == "running"

    finished = await BashJobTool().execute(job_id=started["job_id"], wait_seconds=5)

    assert finished == {
        "job_id": started["job_id"],
        "command": "sleep 0.3; echo built",
        "status": "finished",
        "exit_code": 0,
        "output": "built\n",
    }


@pytest.mark.asyncio
async def test_bash_job_reports_an_unknown_job() -> None:
    result = await BashJobTool().execute(job_id="nope")

    assert "No job 'nope'" in result["error"]


def test_bash_job_may_be_called_again_with_the_same_arguments() -> None:
    assert BashJobTool().repeatable
    assert not BashTool().repeatable


@pytest.mark.asyncio
async def test_bash_job_checks_the_latest_job_without_a_job_id() -> None:
    started = await BashTool().execute(command="echo last", background=True)

    result = await BashJobTool().execute(wait_seconds=5)

    assert started["job_id"].startswith("job_")
    assert result["job_id"] == started["job_id"]
    assert result["output"] == "last\n"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.mark.asyncio
async def test_stopping_a_job_stops_what_it_started(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    command = f"sleep 30 & echo $! > {pid_file}; wait"
    started = await BashTool().execute(command=command, background=True)
    for _ in range(50):
        if pid_file.exists() and pid_file.read_text().strip():
            break
        await asyncio.sleep(0.05)
    child = int(pid_file.read_text())

    result = await BashJobTool().execute(job_id=started["job_id"], stop=True)

    assert result["status"] == "stopped"
    await asyncio.sleep(0.1)
    assert not _alive(child)


@pytest.mark.asyncio
async def test_exiting_stops_running_jobs_and_deletes_their_logs() -> None:
    started = await BashTool().execute(command="sleep 30", background=True)
    job = bash._JOBS[started["job_id"]]  # noqa: SLF001

    bash._stop_all_jobs()  # noqa: SLF001

    await asyncio.wait_for(job.process.wait(), 5)
    assert job.process.returncode is not None
    assert not job.log.parent.exists()
    assert bash._JOBS == {}  # noqa: SLF001
