"""Sandboxed code execution environment for running untrusted code safely."""

import asyncio
from typing import Any

from sensai.features.tools.tool import Tool

from .sandboxed_docker import SandboxedDocker


class SandboxedCode(Tool):
    """A tool for executing python code in a sandboxed environment."""

    def __init__(self) -> None:
        """Initialize the SandboxedCode tool."""
        super().__init__(
            name="sandboxed_code",
            description=(
                "Execute Python code or Bash commands in an isolated sandbox. "
                "Set language to 'python' for Python source or 'bash' for shell commands. "
                "Use the Bash sandbox ONLY when you detect a potentially dangerous command "
                "that could harm the host computer, such as destructive file operations "
                "or harmful system changes. "
                "For Bash commands assessed as safe, use the direct host Bash execution "
                "tool when available instead of this sandbox. "
                "Preserve line breaks, indentation, and quoting required by the chosen language. "
                "Provide raw source without Markdown fences. "
                "In JSON, encode source line breaks as \\n, not as literal "
                "backslash-n sequences after JSON decoding."
            ),
            tool_type="function",
            parameters={
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "enum": ["python", "bash"],
                        "description": "The language used by code: Python source or Bash commands.",
                    },
                    "code": {
                        "type": "string",
                        "description": (
                            "Python source or Bash commands matching language, "
                            "with preserved line breaks and no Markdown fences."
                        ),
                    },
                },
                "required": ["language", "code"],
            },
        )

    def run_in_sandbox(self, language: str, code: str) -> Any:
        """Build the sandbox image and execute code in the worker thread."""
        return SandboxedDocker(language).run_code(code)

    async def execute(self, *_args: Any, **kwargs: Any) -> dict[str, Any]:
        """Execute the provided code in a sandboxed environment.

        Args:
            *_args: Unused positional arguments.
            **kwargs: Keyword arguments containing the code to execute.

        Returns:
            dict[str, Any]: The result of the code execution.
        """
        code = kwargs.get("code", "")
        language = kwargs.get("language", "python").lower()
        docker_output = await asyncio.to_thread(self.run_in_sandbox, language, code)
        return {"result": f"Executed code: {code}", "output": docker_output}
