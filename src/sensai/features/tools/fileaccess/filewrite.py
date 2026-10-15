"""The file write tool for writing content to a file."""

from pathlib import Path
from typing import Any

from sensai.features.tools.tool import Tool

from .fileperms import can_write_to_file


class FileWrite(Tool):
    """Tool for writing content to a file."""

    def __init__(self) -> None:
        """Initialize the FileWrite tool definition."""
        super().__init__(
            name="file_write",
            description=(
                "Write content to a file."
                "The file must be accessible and writable by the system."
                "If the file already exists, it will be overwritten. If it does not exist, it will be created."
            ),
            tool_type="function",
            parameters={
                "type": "object",
                "required": ["file_path", "content"],
                "properties": {
                    "file_path": {"type": "string", "description": "The path to the file to write"},
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file",
                    },
                },
            },
            safe=False,
        )

    def execute(self, *_args: Any, **kwargs: Any) -> dict[str, Any]:
        """Execute the file write tool's functionality.

        Args:
            *_args: Unused positional arguments.
            **kwargs: Keyword arguments for the tool's execution.

        Returns:
            dict[str, Any]: A success message or an error message.
        """
        file_path = kwargs.get("file_path", "Unknown File Path")
        if not isinstance(file_path, str):
            return {"file_path": file_path, "error": "Invalid file path. Must be a string."}
        content = kwargs.get("content", "Unknown Content")
        if not isinstance(content, str):
            return {"file_path": file_path, "error": "Invalid content. Must be a string."}
        try:
            if not can_write_to_file(file_path=file_path):
                return {"file_path": file_path, "error": "File is not writable (Access Denied)."}
            if not Path(file_path).parent.exists():
                return {"file_path": file_path, "error": "Directory does not exist."}
            if Path(file_path).exists() and not Path(file_path).is_file():
                return {"file_path": file_path, "error": "Path exists but is not a file."}
            if not Path(file_path).exists():
                Path(file_path).touch()
            Path(file_path).write_text(content, encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return {"file_path": file_path, "error": str(e)}
        return {"file_path": file_path, "content": content, "document": file_path}
