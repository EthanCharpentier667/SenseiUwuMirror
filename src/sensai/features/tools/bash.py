"""Bash tools: run a command on the host, in the foreground or as a background job."""

import asyncio
import atexit
import contextlib
import os
import shutil
import signal
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sensai.features.tools.tool import Tool

TIMEOUT_SECONDS = 30
MAX_OUTPUT_CHARS = 8000
MAX_WAIT_SECONDS = 120
STOP_GRACE_SECONDS = 3


@dataclass
class Job:
    """A command running in the background, its output going to a log file."""

    command: str
    process: asyncio.subprocess.Process
    log: Path


_JOBS: dict[str, Job] = {}


def _signal_group(process: asyncio.subprocess.Process, sig: signal.Signals) -> None:
    """Send a signal to a command's whole process group: bash and all it started.

    Each command runs in its own group (``start_new_session``), so e.g. the program
    ``xmake run`` launched is stopped along with bash, instead of being left running.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(process.pid, sig)


async def _stop(process: asyncio.subprocess.Process) -> None:
    """Ask a command's process group to stop, then kill it if it hasn't in time."""
    _signal_group(process, signal.SIGTERM)
    try:
        await asyncio.wait_for(process.wait(), STOP_GRACE_SECONDS)
    except TimeoutError:
        _signal_group(process, signal.SIGKILL)
        await process.wait()


def _stop_all_jobs() -> None:
    """Stop every job still running and delete their logs, as Sensai exits.

    Runs from ``atexit``, once the event loop may be gone, so it signals the process
    groups directly instead of awaiting them: SIGTERM, a short grace, then SIGKILL.
    """
    running = [job for job in _JOBS.values() if job.process.returncode is None]
    for job in running:
        _signal_group(job.process, signal.SIGTERM)
    if running:
        time.sleep(0.5)
        for job in running:
            _signal_group(job.process, signal.SIGKILL)
    for job in _JOBS.values():
        shutil.rmtree(job.log.parent, ignore_errors=True)
    _JOBS.clear()


atexit.register(_stop_all_jobs)


def _tail(text: str) -> str:
    """The end of an output, where a build's errors and result are."""
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return f"[… {len(text) - MAX_OUTPUT_CHARS} characters cut]\n{text[-MAX_OUTPUT_CHARS:]}"


class BashTool(Tool):
    """Run a bash command on the host, in the foreground or as a background job."""

    def __init__(self) -> None:
        """Initialize the Bash tool definition."""
        super().__init__(
            name="bash_tool",
            group="bash",
            description=(
                "Execute a bash command on the user's machine. Commands run in the "
                f"foreground for at most {TIMEOUT_SECONDS}s. For long commands (builds, "
                "tests, servers), set background to true: it returns a job_id at once, "
                "so other tools can be used meanwhile; check the job with bash_job."
            ),
            tool_type="function",
            parameters={
                "type": "object",
                "required": ["command"],
                "properties": {
                    "command": {"type": "string", "description": "The bash command to execute"},
                    "background": {
                        "type": "boolean",
                        "description": "Run as a background job and return its job_id at once.",
                    },
                },
            },
            safe=False,
        )

    async def execute(self, *_args: Any, **kwargs: Any) -> dict[str, Any]:
        """Run the command, or start it as a background job.

        Args:
            *_args: Unused positional arguments.
            **kwargs: ``command``, and ``background`` to start it as a job.

        Returns:
            dict[str, Any]: The exit code and output, or the started job's id.
        """
        command = kwargs.get("command")
        if not isinstance(command, str) or not command.strip():
            return {"error": "Invalid command. Must be a non-empty string."}
        if kwargs.get("background"):
            return await self._start_job(command)
        process = await asyncio.create_subprocess_exec(
            "bash",
            "-c",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), TIMEOUT_SECONDS)
        except TimeoutError:
            await _stop(process)
            return {
                "command": command,
                "error": f"Timed out after {TIMEOUT_SECONDS}s and was stopped. "
                "Run it again with background set to true.",
            }
        text = _tail(output.decode(errors="replace"))
        return {"command": command, "exit_code": process.returncode, "output": text}

    @staticmethod
    async def _start_job(command: str) -> dict[str, Any]:
        """Start the command in the background, its output going to a log file.

        The output goes to a file rather than a pipe: nothing reads a pipe while the job
        runs, and a full one would block the command.
        """
        job_id = f"job_{len(_JOBS) + 1}"
        log = Path(tempfile.mkdtemp(prefix="sensai-job-")) / "output.log"
        with log.open("wb") as output:
            process = await asyncio.create_subprocess_exec(
                "bash",
                "-c",
                command,
                stdout=output,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
        _JOBS[job_id] = Job(command, process, log)
        return {"command": command, "job_id": job_id, "status": "running"}


class BashJobTool(Tool):
    """Check on a background job started by bash_tool, optionally waiting for it."""

    def __init__(self) -> None:
        """Initialize the Bash job tool definition."""
        super().__init__(
            name="bash_job",
            group="bash",
            description=(
                "Check a background job started by bash_tool: whether it still runs, its "
                "exit code and the end of its output. Without job_id, checks the latest "
                "job. wait_seconds waits for it to finish "
                f"(at most {MAX_WAIT_SECONDS}s) instead of answering at once; stop ends "
                "it, with everything it started (e.g. a program it launched)."
            ),
            tool_type="function",
            parameters={
                "type": "object",
                "required": [],
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job_id bash_tool gave. Default: the latest job.",
                    },
                    "wait_seconds": {
                        "type": "integer",
                        "description": "How long to wait for the job to finish.",
                    },
                    "stop": {
                        "type": "boolean",
                        "description": "Stop the job and everything it started.",
                    },
                },
            },
            safe=True,
            repeatable=True,
        )

    async def execute(self, *_args: Any, **kwargs: Any) -> dict[str, Any]:
        """Report the job's status and the end of its output.

        Args:
            *_args: Unused positional arguments.
            **kwargs: ``job_id`` (the latest job when missing), ``wait_seconds`` to
                wait for the job to finish, and ``stop`` to stop it.

        Returns:
            dict[str, Any]: The job's status, exit code (once finished) and output.
        """
        job_id = kwargs.get("job_id") or next(reversed(_JOBS), None)
        job = _JOBS.get(str(job_id))
        if job is None:
            return {"error": f"No job {job_id!r}. Known jobs: {list(_JOBS)}."}
        stopped = bool(kwargs.get("stop"))
        if stopped:
            await _stop(job.process)
        wait = kwargs.get("wait_seconds")
        if isinstance(wait, int) and wait > 0 and job.process.returncode is None:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(job.process.wait(), min(wait, MAX_WAIT_SECONDS))
        output = _tail(job.log.read_text(encoding="utf-8", errors="replace"))
        if job.process.returncode is None:
            return {"job_id": job_id, "command": job.command, "status": "running", "output": output}
        return {
            "job_id": job_id,
            "command": job.command,
            "status": "stopped" if stopped else "finished",
            "exit_code": job.process.returncode,
            "output": output,
        }
