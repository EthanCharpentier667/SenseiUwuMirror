"""Sandboxed code execution environment for running untrusted code safely."""

import asyncio
from typing import Any

from .sandboxed_docker import SandboxedDocker
from .tool import Tool


class SandboxedCode(Tool):
    """A tool for executing python code in a sandboxed environment."""

    def __init__(self) -> None:
        """Initialize the SandboxedCode tool."""
        super().__init__(
            name="sandboxed_code",
            description=(
                "Execute valid Python code in an isolated sandbox. "
                "Preserve line breaks and indentation, especially for compound "
                "statements such as for, if, def, and class. "
                "Provide raw Python source without Markdown fences. "
                "In JSON, encode source line breaks as \\n, not as literal "
                "backslash-n sequences after JSON decoding."
            ),
            tool_type="function",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The python code to execute in the sandbox.",
                    }
                },
                "required": ["code"],
            },
        )

    async def execute(self, *_args: Any, **kwargs: Any) -> dict[str, Any]:
        """Execute the provided code in a sandboxed environment.

        Args:
            *_args: Unused positional arguments.
            **kwargs: Keyword arguments containing the code to execute.

        Returns:
            dict[str, Any]: The result of the code execution.
        """
        code = kwargs.get("code", "")
        docker_sandbox = SandboxedDocker()
        docker_output = await asyncio.to_thread(docker_sandbox.run_code, code)
        return {"result": f"Executed code: {code}", "output": docker_output}
