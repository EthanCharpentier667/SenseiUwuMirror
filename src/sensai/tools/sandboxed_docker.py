"""A Docker container for running code in a sandboxed environment."""

from pathlib import Path
from typing import Any

import docker


class SandboxedDocker:
    """A Docker container for running code in a sandboxed environment."""

    def __init__(self) -> None:
        """Initialize the SandboxedDocker container."""

    def _build_image(self) -> Any:
        """Build the Docker image for the sandboxed environment."""
        docker_directory = Path(__file__).resolve().parent / "docker"
        client = docker.from_env()
        result = client.images.build(
            path=str(docker_directory), tag="sensai-sandboxed:dev", rm=True
        )
        return result[0].id

    def run_code(self, code: str) -> Any:
        """Run the provided code in the Docker container.

        Args:
            code (str): The python code to execute in the sandboxed environment.
        """
        client = docker.from_env()
        container = client.containers.run(
            image=self._build_image(),
            command=["-c", code],
            detach=True,
            stdout=True,
            stderr=True,
            cpu_shares=512,  # Limit CPU usage
            cap_drop=["ALL"],  # Drop all capabilities
            mem_limit="256m",  # Limit memory usage
            network_disabled=True,  # Disable network access
            security_opt=["no-new-privileges"],  # Prevent privilege escalation
            pids_limit=64,  # Limit the number of processes
            privileged=False,  # Do not run in privileged mode
        )
        _result = container.wait(timeout=20)
        if _result["StatusCode"] != 0:
            error_output = container.logs(stderr=True).decode("utf-8")
            container.remove()
            raise RuntimeError(f"Error executing code in sandboxed environment: {error_output}")
        output = container.logs().decode("utf-8")
        container.remove()
        return output
