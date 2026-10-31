"""Screenshot tool for capturing and processing screenshots."""

import base64
import io
import tempfile
from pathlib import Path
from typing import Any

import pyscreenshot

from sensai.features.tools.tool import Tool

SAVE_DIRECTORY = Path(tempfile.gettempdir()) / "sensai"
SAVE_PATH = SAVE_DIRECTORY / "screenshot.jpg"
MAX_SIZE = (1920, 1080)
JPEG_QUALITY = 80


class Screenshot(Tool):
    """A tool for capturing the screen and showing it to the model."""

    def __init__(self) -> None:
        """Initialize the Screenshot tool definition."""
        super().__init__(
            name="screenshot",
            group="screenshot",
            description=(
                "Capture a screenshot of the user's current screen. The image is shown to "
                "you right away, to describe the screen or answer questions about it."
            ),
            tool_type="function",
            parameters={
                "type": "object",
                "required": [],
                "properties": {},
            },
            safe=False,
            requires={"vision"},
        )

    def execute(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        """Execute the screenshot tool's functionality.

        Args:
            *_args: Unused positional arguments.
            **_kwargs: Unused keyword arguments.

        Returns:
            dict[str, Any]: The result of the screenshot tool's execution.
        """
        return self.capture()

    def capture(self) -> dict[str, Any]:
        """Capture the screen, save it as a JPEG and return it in base64.

        The image is downscaled to ``MAX_SIZE`` and converted to RGB (JPEG has no alpha),
        so it stays small enough to send to the model.

        Returns:
            dict[str, Any]: Where the screenshot was saved, and the image in ``images``.
        """
        image: Any = pyscreenshot.grab()
        image = image.convert("RGB")
        image.thumbnail(MAX_SIZE)
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=JPEG_QUALITY)
        SAVE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        SAVE_PATH.write_bytes(buffer.getvalue())
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return {"message": f"Screenshot saved to {SAVE_PATH}.", "images": [encoded]}
