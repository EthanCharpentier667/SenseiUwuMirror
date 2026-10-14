"""A Docker container for running code in a sandboxed environment."""

import codecs
import socket
import tarfile
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryFile
from typing import Any

import docker

MAX_OUTPUT_BYTES = 64 * 1024
DOCKERFILE_PYTHON = "Dockerfile.python"
DOCKERFILE_BASH = "Dockerfile.bash"


def filter_member(member: tarfile.TarInfo) -> tarfile.TarInfo | None:
    """Keep ordinary project files without hidden files or local Python environments."""
    excluded = {"__pycache__", "venv"}
    parts = Path(member.name).parts
    if any(part.startswith(".") or part in excluded for part in parts):
        return None
    if not (member.isfile() or member.isdir()):
        return None
    member.uid = 10001
    member.gid = 10001
    member.uname = ""
    member.gname = ""
    member.mode |= 0o700 if member.isdir() else 0o600
    return member


def copy_project(container: Any, project_directory: Path) -> None:
    """Send an archive to the container's tar process through standard input."""
    with TemporaryFile() as archive_file:
        with tarfile.open(fileobj=archive_file, mode="w") as archive:
            archive.add(
                project_directory,
                arcname=".",
                filter=filter_member,
            )
        archive_file.seek(0)
        with closing(container.attach_socket(params={"stdin": True, "stream": True})) as connection:
            transport = getattr(connection, "_sock", connection)
            transport.settimeout(20)
            while chunk := archive_file.read(MAX_OUTPUT_BYTES):
                transport.sendall(chunk)
            transport.shutdown(socket.SHUT_WR)


class SandboxedDocker:
    """A Docker container for running code in a sandboxed environment."""

    def __init__(self, language: str) -> None:
        """Initialize the SandboxedDocker container."""
        self.type = language
        if language == "python":
            self.image = self._build_image_python()
        elif language == "bash":
            self.image = self._build_image_bash()
        else:
            raise ValueError("Unsupported type. Please use 'python' or 'bash'.")

    def _build_image_python(self) -> Any:
        """Build the Docker image for the sandboxed environment."""
        docker_directory = Path(__file__).resolve().parent / "docker"
        client = docker.from_env()
        result = client.images.build(
            path=str(docker_directory),
            tag="sensai-sandboxed:dev",
            rm=True,
            dockerfile=DOCKERFILE_PYTHON,
        )
        return result[0].id

    def _build_image_bash(self) -> Any:
        """Build the Docker image for the sandboxed environment."""
        docker_directory = Path(__file__).resolve().parent / "docker"
        client = docker.from_env()
        result = client.images.build(
            path=str(docker_directory),
            tag="sensai-sandboxed:dev",
            rm=True,
            dockerfile=DOCKERFILE_BASH,
        )
        return result[0].id

    def _read_output(self, container: Any) -> str:
        """Read bounded logs, omitting an incomplete UTF-8 character at truncation."""
        output = bytearray()
        truncated = False
        with closing(container.logs(stream=True, follow=False)) as logs:
            for chunk in logs:
                remaining = MAX_OUTPUT_BYTES - len(output)
                output.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    truncated = True
                    break
        decoder = codecs.getincrementaldecoder("utf-8")()
        return decoder.decode(output, final=not truncated)

    def run_code(self, code: str) -> Any:
        """Run the provided code in the Docker container.

        Args:
            code (str): The python code to execute in the sandboxed environment.
        """
        client = docker.from_env()
        command = ["-c", code]
        if self.type == "bash":
            command = [
                "-c",
                (
                    "tar --extract --file=- --directory=/workspace --no-same-owner "
                    '&& exec /bin/bash -c "$1"'
                ),
                "sensai-sandbox",
                code,
            ]
        container = client.containers.run(
            image=self.image,
            command=command,
            stdin_open=self.type == "bash",
            detach=True,
            stdout=True,
            stderr=True,
            nano_cpus=500_000_000,  # Limit CPU usage to half a core
            cap_drop=["ALL"],  # Drop all capabilities
            mem_limit="512m",  # Limit memory usage
            read_only=True,
            tmpfs={
                "/workspace": "rw,noexec,nosuid,nodev,size=512m,uid=10001,gid=10001,mode=0700",
                "/tmp": (  # noqa: S108 - Private, size-limited container mount.
                    "rw,noexec,nosuid,nodev,size=16m,uid=10001,gid=10001,mode=0700"
                ),
            },
            network_disabled=True,  # Disable network access
            security_opt=["no-new-privileges"],  # Prevent privilege escalation
            pids_limit=64,  # Limit the number of processes
            privileged=False,  # Do not run in privileged mode
            log_config=docker.types.LogConfig(
                type="local", config={"max-size": "1m", "max-file": "1", "compress": "false"}
            ),
        )
        try:
            if self.type == "bash":
                copy_project(container, Path.cwd())
            result = container.wait(timeout=20)
            output = self._read_output(container)
            if result["StatusCode"] != 0:
                raise RuntimeError(f"Error executing code in sandboxed environment: {output}")
            return output
        finally:
            container.remove(force=True)
