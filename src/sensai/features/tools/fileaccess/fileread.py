"""The file read tool for reading the contents of a file."""

from pathlib import Path
from typing import Any

from sensai.features.tools.tool import Tool

from .fileperms import can_read_file


class FileRead(Tool):
    """Tool reading a file's contents for the model."""

    def __init__(self) -> None:
        """Initialize the FileRead tool definition."""
        super().__init__(
            name="file_read",
            group="files",
            description=(
                "Read the contents of a file and return it as a string. "
                "The file must be accessible and readable by the system."
            ),
            tool_type="function",
            parameters={
                "type": "object",
                "required": ["file_path"],
                "properties": {
                    "file_path": {"type": "string", "description": "The path to the file to read"}
                },
            },
            safe=False,
        )

    def execute(self, *_args: Any, **kwargs: Any) -> dict[str, Any]:
        """Execute the file read tool's functionality.

        Args:
            *_args: Unused positional arguments.
            **kwargs: Keyword arguments for the tool's execution.

        Returns:
            dict[str, Any]: The contents of the specified file. Its "document" key asks
                the app to ingest the file for RAG, so later turns can retrieve it.
        """
        file_path = kwargs.get("file_path", "Unknown File Path")
        if not isinstance(file_path, str):
            return {"file_path": file_path, "error": "Invalid file path. Must be a string."}
        if not Path(file_path).is_file():
            return {"file_path": file_path, "error": "File not found (or not a regular file)."}
        if not can_read_file(file_path=file_path):
            return {"file_path": file_path, "error": "File is not readable (Access Denied)."}
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return {"file_path": file_path, "error": str(e)}
        return {"file_path": file_path, "content": content, "document": file_path}
